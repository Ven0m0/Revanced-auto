"""Download manager module for unified APK downloads from multiple sources."""

from __future__ import annotations

from dataclasses import dataclass

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


@dataclass
class DownloadManager:
    """Coordinates APK downloads across multiple sources with failover."""

    def __init__(self, http_client: HttpClient) -> None:
        """Initialize DownloadManager.

        Args:
            http_client: HTTP client for requests.

        """
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
