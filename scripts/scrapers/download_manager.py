"""Download manager module for unified APK downloads from multiple sources."""

from __future__ import annotations

import asyncio
import re
import threading
from dataclasses import dataclass
from pathlib import Path

from scripts.scrapers.apkmirror import APKMirror
from scripts.scrapers.apkmonk import APKMonkScraper
from scripts.scrapers.apkpure import APKPureScraper
from scripts.scrapers.aptoide import AptoideScraper
from scripts.scrapers.archive import ArchiveScraper
from scripts.scrapers.base import DownloadSource, ScraperBase
from scripts.scrapers.uptodown import UptodownScraper
from scripts.utils.network import HttpClient

ARCH_NORMALIZATION: dict[str, str] = {
    "arm-v7a": "armeabi-v7a",
}


def _reset_scraper_session(scraper: ScraperBase) -> None:
    """Drop a scraper's cached httpx.AsyncClient before a new asyncio.run() call.

    ScraperBase.session lazily creates and caches an AsyncClient bound to
    whatever event loop is running at creation time. DownloadManager makes
    one asyncio.run() call per resolve()/download() invocation -- each call
    gets its own fresh event loop -- so a session cached from a prior call
    breaks with "Event loop is closed". Resetting forces a fresh client bound
    to the loop that's about to run.
    """
    scraper._session = None  # noqa: SLF001


def _version_sort_key(version: str) -> tuple[int, ...]:
    """Sort key for dotted version strings, e.g. ``19.09.36`` > ``9.9.9``.

    ponytail: numeric-only comparison, ignores suffixes like "-beta3" beyond
    their leading digits. Good enough for picking the newest stable release;
    revisit with proper semver parsing if pre-release ordering matters.
    """
    parts = re.findall(r"\d+", version)
    return tuple(int(p) for p in parts) if parts else (0,)


@dataclass
class DownloadManager:
    """Coordinates APK downloads across multiple sources with failover."""

    def __init__(self, http_client: HttpClient) -> None:
        """Initialize DownloadManager.

        Args:
            http_client: HTTP client for requests.

        """
        self._scrapers: dict[DownloadSource, ScraperBase] = {}
        # resolve()/download() are called concurrently across
        # ThreadPoolExecutor worker threads (one per app/arch build
        # variant), but each call's asyncio.run() creates a fresh event
        # loop while reusing the same cached scraper (and its
        # httpx.AsyncClient / internal locks). Serializing calls here is
        # simpler and more correct than making the scrapers themselves
        # thread-safe, and avoids self-inflicted rate limiting from
        # hammering a source concurrently.
        self._lock = threading.Lock()

    def _get_scraper(self, source: DownloadSource) -> ScraperBase:
        """Get or create scraper instance for source.

        Args:
            source: Download source identifier.

        Returns:
            ScraperBase instance for the source.

        """
        if source not in self._scrapers:
            match source:
                case DownloadSource.APKMIRROR:
                    self._scrapers[source] = APKMirror()
                case DownloadSource.APKMonk:
                    self._scrapers[source] = APKMonkScraper()
                case DownloadSource.UPTODOWN:
                    self._scrapers[source] = UptodownScraper()
                case DownloadSource.APKPURE:
                    self._scrapers[source] = APKPureScraper()
                case DownloadSource.APTOIDE:
                    self._scrapers[source] = AptoideScraper()
                case DownloadSource.ARCHIVE:
                    self._scrapers[source] = ArchiveScraper()
                case _:
                    msg = f"Unsupported download source: {source}"
                    raise ValueError(msg)
        return self._scrapers[source]

    def resolve(
        self,
        app_id: str,
        source: DownloadSource,
        *,
        timeout: int = 300,
    ) -> tuple[str, str]:
        """Resolve the latest available (non-alpha/beta) version for an app.

        Args:
            app_id: Package identifier as expected by the source's scraper
                (e.g. an APKMirror URL slug like ``google-inc/youtube``).
            source: Download source to query.
            timeout: Unused; scrapers manage their own request timeouts.

        Returns:
            Tuple of (version_string, version_string). No scraper exposes a
            separate Android versionCode, so both elements carry the version
            string; callers that need a real versionCode must look elsewhere.
        """
        del timeout
        with self._lock:
            scraper = self._get_scraper(source)
            _reset_scraper_session(scraper)
            # resolve() only needs *a* version number, not a specific
            # installable variant -- not every app ships a plain
            # "universal"/"nodpi"/"APK" build (e.g. APKMirror's YouTube Music
            # releases are BUNDLE-only, split per-arch, with dpi *ranges*
            # instead of "nodpi"). match_any skips APKMirror's bundle/dpi/arch
            # equality checks, accepting whatever variant a release has. It's
            # an APKMirror-only kwarg; other scrapers ignore unknown kwargs
            # via **kwargs.
            kwargs: dict[str, bool] = {"match_any": True}
            versions = asyncio.run(scraper.get_versions(app_id, **kwargs))
        if not versions:
            msg = f"No versions found for {app_id!r} on {source.value}"
            raise ValueError(msg)
        latest = max(versions, key=lambda v: _version_sort_key(v.version))
        return latest.version, latest.version

    def download(
        self,
        app_id: str,
        version: str,
        output_path: Path,
        source: DownloadSource,
        *,
        arch: str | None = None,
        dpi: str | None = None,
        timeout: int = 300,
    ) -> Path:
        """Download a stock APK from the given source.

        Args:
            app_id: Package identifier as expected by the source's scraper.
            version: Version to download.
            output_path: Where to save the downloaded APK.
            source: Download source to use.
            arch: Target architecture, if the source supports filtering by it.
            dpi: Target DPI, if the source supports filtering by it.
            timeout: Unused; scrapers manage their own request timeouts.

        Returns:
            Path to the downloaded APK.
        """
        del timeout
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with self._lock:
            scraper = self._get_scraper(source)
            _reset_scraper_session(scraper)
            kwargs: dict[str, str] = {}
            if arch:
                # Only APKMirror's ArchType expects "armeabi-v7a"; other
                # scrapers (e.g. Archive.org) key VersionInfo.arch off the raw
                # filename convention ("arm-v7a"), so normalizing there would
                # break the exact-match lookup in their download().
                kwargs["arch"] = self._normalize_arch(arch) if source == DownloadSource.APKMIRROR else arch
            if dpi:
                kwargs["dpi"] = dpi

            result = asyncio.run(scraper.download(app_id, version, output_path, **kwargs))
        if not result.success or result.file_path is None:
            msg = result.error or f"Failed to download {app_id!r} {version} from {source.value}"
            raise RuntimeError(msg)
        return result.file_path

    def _normalize_arch(self, arch: str) -> str:
        """Normalize architecture string.

        Converts shorthand architecture names to their canonical form.

        Args:
            arch: Architecture string (e.g., "arm-v7a").

        Returns:
            Normalized architecture string (e.g., "armeabi-v7a").

        """
        return ARCH_NORMALIZATION.get(arch, arch)

    def close(self) -> None:
        """Close all scraper sessions."""
        for scraper in self._scrapers.values():
            scraper.close()
        self._scrapers.clear()

    def __del__(self) -> None:
        """Cleanup on deletion."""
        self.close()
