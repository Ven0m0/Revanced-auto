"""Base scraper class and common types for all APK download sources."""

from __future__ import annotations

import time as _time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

import httpx

if TYPE_CHECKING:
    from pathlib import Path

APK_ARCHIVE_URL = "https://archive.org"


class DownloadSource(Enum):
    """Enumeration of supported APK download sources."""

    APKMIRROR = "apkmirror"
    UPTODOWN = "uptodown"
    APKPURE = "apkpure"
    APTOIDE = "aptoide"
    ARCHIVE = "archive"
    APKMONK = "apkmonk"


@dataclass
class VersionInfo:
    """Information about a specific APK version."""

    version: str
    url: str | None = None
    arch: str | None = None
    dpi: str | None = None


@dataclass
class DownloadResult:
    """Result of an APK download operation."""

    success: bool
    file_path: Path | None = None
    version: str | None = None
    error: str | None = None


class ScraperBase(ABC):
    """Base class for all APK scrapers."""

    MAX_RETRIES = 4
    BASE_DELAY = 1.0
    CACHE_TTL = 3600

    def __init__(self, source: DownloadSource) -> None:
        """Initialize the scraper.

        Args:
            source: The download source identifier.

        """
        self.source = source
        self._session: httpx.Client | None = None
        self._cache: dict[str, tuple[float, object]] = {}

    @property
    def session(self) -> httpx.Client:
        """Get or create the HTTPX sync client.

        Returns:
            An httpx.Client instance.

        """
        if self._session is None:
            self._session = httpx.Client(
                timeout=30.0,
                follow_redirects=True,
                headers={
                    "User-Agent": "Mozilla/5.0 (compatible; APKScraper/1.0)",
                },
            )
        return self._session

    def _get_cache(self, key: str) -> object | None:
        if key in self._cache:
            timestamp, value = self._cache[key]
            if timestamp + self.CACHE_TTL > _time.time():
                return value
            del self._cache[key]
        return None

    def _set_cache(self, key: str, value: object) -> None:
        self._cache[key] = (_time.time(), value)

    def _clear_cache(self) -> None:
        self._cache.clear()

    def _request_with_retry(
        self,
        url: str,
        method: str = "GET",
        **kwargs: object,
    ) -> httpx.Response:
        delay = self.BASE_DELAY
        last_error: Exception | None = None

        for attempt in range(self.MAX_RETRIES):
            try:
                response = self.session.request(method, url, **kwargs)
                response.raise_for_status()
            except (httpx.HTTPError, httpx.TimeoutException) as e:
                last_error = e
                if attempt < self.MAX_RETRIES - 1:
                    _time.sleep(delay)
                    delay *= 2
            else:
                return response

        msg = f"Request failed after {self.MAX_RETRIES} retries: {url}"
        raise RuntimeError(msg) from last_error

    def get(self, url: str, *, use_cache: bool = True) -> httpx.Response:
        """Perform a GET request with caching.

        Args:
            url: The URL to fetch.
            use_cache: Whether to use the internal cache.

        Returns:
            An httpx.Response object.

        """
        cache_key = f"get:{url}"
        if use_cache:
            cached = self._get_cache(cache_key)
            if cached is not None:
                return cached  # type: ignore[return-value]

        response = self._request_with_retry(url)
        if use_cache:
            self._set_cache(cache_key, response)
        return response

    async def get_versions(self, pkg_name: str, **kwargs: object) -> list[VersionInfo]:
        """Get available versions for an app.

        Args:
            pkg_name: Package name.
            **kwargs: Additional arguments.

        Returns:
            List of VersionInfo objects.

        """
        raise NotImplementedError

    async def download(
        self,
        pkg_name: str,
        version: str | None,
        output_path: Path,
        **kwargs: object,
    ) -> DownloadResult:
        """Download specific version of an app.

        Args:
            pkg_name: Package name.
            version: Version string.
            output_path: Output file path.
            **kwargs: Additional arguments.

        Returns:
            A DownloadResult object.

        """
        raise NotImplementedError

    @abstractmethod
    def get_package_name(self, url: str) -> str | None:
        """Extract package name from URL."""

    def close(self) -> None:
        """Close the HTTPX session."""
        if self._session is not None:
            self._session.close()
            self._session = None

    def __del__(self) -> None:
        """Close the session on deletion."""
        self.close()
