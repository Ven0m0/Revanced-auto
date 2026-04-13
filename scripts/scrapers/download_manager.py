"""Download manager module for unified APK downloads from multiple sources."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from scripts.scrapers.apkmirror import APKMirror
from scripts.scrapers.apkmonk import APKMonkScraper
from scripts.scrapers.apkpure import APKPureScraper
from scripts.scrapers.aptoide import AptoideScraper
from scripts.scrapers.archive import ArchiveScraper
from scripts.scrapers.base import DownloadResult, DownloadSource, ScraperBase
from scripts.scrapers.uptodown import UptodownScraper

if TYPE_CHECKING:
    from scripts.builder.config import AppConfig
    from scripts.utils.network import HttpClient


ARCH_NORMALIZATION: dict[str, str] = {
    "arm-v7a": "armeabi-v7a",
}


@dataclass
class DownloadManager:
    """Coordinates APK downloads across multiple sources with failover.

    Attributes:
        http: HTTP client for making requests.

    Example:
        >>> client = HttpClient()
        >>> manager = DownloadManager(client)
        >>> result = await manager.download_apk(
        ...     package="com.example.app",
        ...     version=None,
        ...     output_dir=Path("output"),
        ...     sources=[DownloadSource.APKMIRROR, DownloadSource.UPTODOWN],
        ... )
    """

    http: HttpClient

    def __init__(self, http_client: HttpClient) -> None:
        """Initialize DownloadManager.

        Args:
            http_client: HTTP client for requests.

        """
        self.http = http_client
        self._scrapers: dict[DownloadSource, ScraperBase] = {}

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
                case DownloadSource.APKMONK:
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

    def _normalize_arch(self, arch: str) -> str:
        """Normalize architecture string.

        Converts shorthand architecture names to their canonical form.

        Args:
            arch: Architecture string (e.g., "arm-v7a").

        Returns:
            Normalized architecture string (e.g., "armeabi-v7a").

        """
        return ARCH_NORMALIZATION.get(arch, arch)

    async def download_apk(
        self,
        package: str,
        version: str | None,
        output_dir: Path,
        sources: list[DownloadSource],
        arch: str = "arm64-v8a",
        dpi: str = "nodpi",
    ) -> DownloadResult:
        """Try each source in order until download succeeds.

        Args:
            package: Package name (e.g., "com.google.android.youtube").
            version: Version string, or None for latest.
            output_dir: Directory to save downloaded APK.
            sources: List of sources to try in order.
            arch: Target architecture (default: arm64-v8a).
            dpi: Target DPI (default: nodpi).

        Returns:
            DownloadResult with success status, file path, and version.

        """
        normalized_arch = self._normalize_arch(arch)
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        errors: list[str] = []

        for source in sources:
            scraper = self._get_scraper(source)

            output_path = output_dir / f"{package}_{version or 'latest'}_{normalized_arch}.apk"

            try:
                result = await scraper.download(package, version, output_path, arch=normalized_arch, dpi=dpi)

                if result.success:
                    return result

                error_msg = f"{source.value}: {result.error or 'Unknown error'}"
                errors.append(error_msg)

            except Exception as e:
                error_msg = f"{source.value}: {e!s}"
                errors.append(error_msg)
                continue

        return DownloadResult(
            success=False,
            file_path=None,
            version=version,
            error=f"All sources failed. Errors: {'; '.join(errors)}",
        )

    def get_package_name(self, url: str) -> str | None:
        """Get package name from any supported URL.

        Args:
            url: URL from any supported source.

        Returns:
            Package name if found, None otherwise.

        """
        patterns: list[tuple[str, re.Pattern[str]]] = [
            ("apkmirror", re.compile(r"apkmirror\.com/apk/([^/]+)/([^/]+)/?")),
            ("uptodown", re.compile(r"https://([^.]+)\.en\.uptodown\.com/android")),
            ("apkpure", re.compile(r"apkpure\.net/[^/]+/([a-zA-Z0-9_.]+)")),
        ]

        for source_name, pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(2) if source_name == "apkmirror" else match.group(1)

        return None

    async def download_from_app_config(
        self,
        app_config: AppConfig,
        output_dir: Path,
    ) -> DownloadResult:
        """Download APK using configuration from AppConfig.

        Args:
            app_config: Application configuration with source settings.
            output_dir: Directory to save downloaded APK.

        Returns:
            DownloadResult with success status and file path.

        """
        package = app_config.name
        version = app_config.version

        arch = "arm64-v8a"
        dpi = "nodpi"

        source_options = app_config.options
        sources: list[DownloadSource] = []

        if source_options.get("apkmirror_dlurl"):
            sources.append(DownloadSource.APKMIRROR)
        if source_options.get("uptodown_dlurl"):
            sources.append(DownloadSource.UPTODOWN)
        if source_options.get("apkpure_dlurl"):
            sources.append(DownloadSource.APKPURE)
        if source_options.get("archive_dlurl"):
            sources.append(DownloadSource.ARCHIVE)
        if source_options.get("aptoide_dlurl"):
            sources.append(DownloadSource.APTOIDE)
        if source_options.get("apkmonk_dlurl"):
            sources.append(DownloadSource.APKMonk)

        if not sources:
            sources = [DownloadSource.APKMIRROR, DownloadSource.UPTODOWN, DownloadSource.APKPURE]

        return await self.download_apk(package, version, output_dir, sources, arch, dpi)

    def close(self) -> None:
        """Close all scraper sessions."""
        for scraper in self._scrapers.values():
            scraper.close()
        self._scrapers.clear()

    def __del__(self) -> None:
        """Cleanup on deletion."""
        self.close()
