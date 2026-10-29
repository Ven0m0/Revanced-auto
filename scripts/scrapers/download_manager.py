"""Download manager module for unified APK downloads from multiple sources."""

from __future__ import annotations

import asyncio
import re
import shutil
import tempfile
import threading
import zipfile
from dataclasses import dataclass
from pathlib import Path

from scripts.scrapers.apkmirror import APKMirror, is_apk_bundle, merge_apkm_splits
from scripts.scrapers.apkmonk import APKMonkScraper
from scripts.scrapers.apkpure import APKPureScraper
from scripts.scrapers.aptoide import AptoideScraper
from scripts.scrapers.archive import ArchiveScraper
from scripts.scrapers.base import DownloadSource, ScraperBase
from scripts.scrapers.github import GitHubScraper
from scripts.scrapers.uptodown import UptodownScraper
from scripts.utils.apk import signer_digests

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


def _is_apk(path: Path) -> bool:
    """True if ``path`` is a zip holding AndroidManifest.xml.

    Scrapers can save an HTML challenge/error page under the .apk name; the
    patcher would otherwise fail much later with an opaque error.
    """
    try:
        with zipfile.ZipFile(path) as zf:
            return "AndroidManifest.xml" in zf.namelist()
    except OSError, zipfile.BadZipFile:
        return False


def _stock_cert_matches(path: Path, expected_cert: str) -> bool:
    """True if the stock APK (or a bundle's ``base.apk``) is signed with ``expected_cert``.

    Must run before the splits are merged: merging drops the original signature.
    """
    if not is_apk_bundle(path):
        return expected_cert in signer_digests(path)
    with tempfile.TemporaryDirectory(prefix="stocksig_") as tmp, zipfile.ZipFile(path) as zf:
        if "base.apk" not in zf.namelist():
            return False
        # Read the member into a fixed name instead of extract(), so a crafted entry name cannot escape tmp.
        base = Path(tmp) / "base.apk"
        with zf.open("base.apk") as src, base.open("wb") as dst:
            shutil.copyfileobj(src, dst)
        return expected_cert in signer_digests(base)


def _bare_version(version: str) -> str:
    return version.strip().removeprefix("v").removeprefix("V")


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

    def __init__(self) -> None:
        """Initialize DownloadManager."""
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
        """Get or create the scraper instance for ``source``."""
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
                case DownloadSource.GITHUB:
                    self._scrapers[source] = GitHubScraper()
        return self._scrapers[source]

    def resolve(
        self,
        app_id: str,
        source: DownloadSource,
        *,
        compatible: list[str] | None = None,
        include_beta: bool = False,
        timeout: int = 300,
    ) -> tuple[str, str]:
        """Resolve the newest available version for an app.

        Args:
            app_id: Package identifier as expected by the source's scraper
                (e.g. an APKMirror URL slug like ``google-inc/youtube``).
            source: Download source to query.
            compatible: Versions the patches support. When non-empty, only
                these are considered; an empty list or None means no filter.
            include_beta: Keep alpha/beta releases (APKMirror only).
            timeout: Unused; scrapers manage their own request timeouts.

        Returns:
            Tuple of (version_string, version_string). No scraper exposes a
            separate Android versionCode, so both elements carry the version
            string; callers that need a real versionCode must look elsewhere.

        Raises:
            ValueError: No versions found, or none is in ``compatible``.
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
            kwargs: dict[str, bool | list[str]] = {"match_any": True, "exclude_alpha_beta": not include_beta}
            if source == DownloadSource.APKMIRROR and compatible:
                # APKMirror's app page lists only recent releases; this lets it look up older compatible ones.
                kwargs["compatible"] = compatible
            versions = asyncio.run(scraper.get_versions(app_id, **kwargs))
        if not versions:
            msg = f"No versions found for {app_id!r} on {source.value}"
            raise ValueError(msg)
        if compatible:
            # GitHub tags carry a "v" prefix that list-versions output lacks.
            allowed = {_bare_version(v) for v in compatible}
            versions = [v for v in versions if _bare_version(v.version) in allowed]
            if not versions:
                msg = f"no patch-compatible version on {source.value}"
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
        expected_cert: str | None = None,
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
            expected_cert: Expected stock signing certificate SHA-256; a mismatch raises.

        Returns:
            Path to the downloaded APK.
        """
        del timeout
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with self._lock:
            scraper = self._get_scraper(source)
            _reset_scraper_session(scraper)
            kwargs: dict[str, str | bool] = {}
            if arch:
                # Only Archive.org keys VersionInfo.arch off the raw filename
                # convention ("arm-v7a"); APKMirror, GitHub asset names,
                # Uptodown and Aptoide all use "armeabi-v7a".
                kwargs["arch"] = arch if source == DownloadSource.ARCHIVE else self._normalize_arch(arch)
            if dpi:
                kwargs["dpi"] = dpi
            if source == DownloadSource.APKMIRROR:
                # The version is exact here, so a beta that is the pinned or
                # resolved release must not be filtered out again.
                kwargs["exclude_alpha_beta"] = False

            result = asyncio.run(scraper.download(app_id, version, output_path, **kwargs))
        if not result.success or result.file_path is None:
            msg = result.error or f"Failed to download {app_id!r} {version} from {source.value}"
            raise RuntimeError(msg)

        path = result.file_path
        if expected_cert and not _stock_cert_matches(path, expected_cert):
            path.unlink(missing_ok=True)
            msg = f"{source.value} stock APK signature mismatch for {app_id!r} {version}"
            raise RuntimeError(msg)
        if is_apk_bundle(path):
            bundle = path if path.suffix == ".apkm" else path.replace(path.with_suffix(".apkm"))
            try:
                with tempfile.TemporaryDirectory(prefix="apkeditor_") as tmp:
                    merge_apkm_splits(Path(tmp), bundle, output_path)
            finally:
                bundle.unlink(missing_ok=True)
            path = output_path
        if not _is_apk(path):
            path.unlink(missing_ok=True)
            msg = f"{source.value} returned a non-APK file for {app_id!r} {version}"
            raise RuntimeError(msg)
        return path

    def _normalize_arch(self, arch: str) -> str:
        """Normalize a shorthand architecture name (e.g. ``arm-v7a``) to its canonical form."""
        return ARCH_NORMALIZATION.get(arch, arch)

    def close(self) -> None:
        """Close all scraper sessions."""
        for scraper in self._scrapers.values():
            scraper.close()
        self._scrapers.clear()

    def __del__(self) -> None:
        """Cleanup on deletion."""
        self.close()
