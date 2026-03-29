"""Base scraper class and common types for all APK download sources."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

import httpx

APK_ARCHIVE_URL = "https://archive.org"


class DownloadSource(Enum):
    APKMIRROR = "apkmirror"
    UPTODOWN = "uptodown"
    APKPURE = "apkpure"
    APTOIDE = "aptoide"
    ARCHIVE = "archive"
    APKMonk = "apkmonk"


@dataclass
class VersionInfo:
    version: str
    url: str | None = None
    arch: str | None = None
    dpi: str | None = None


@dataclass
class DownloadResult:
    success: bool
    file_path: Path | None = None
    version: str | None = None
    error: str | None = None


class ScraperBase(ABC):
    MAX_RETRIES = 4
    BASE_DELAY = 1.0
    CACHE_TTL = 3600

    def __init__(self, source: DownloadSource) -> None:
        self.source = source
        self._session: httpx.Client | None = None
        self._cache: dict[str, tuple[float, object]] = {}

    @property
    def session(self) -> httpx.Client:
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
                return response
            except (httpx.HTTPError, httpx.TimeoutException) as e:
                last_error = e
                if attempt < self.MAX_RETRIES - 1:
                    _time.sleep(delay)
                    delay *= 2

        msg = f"Request failed after {self.MAX_RETRIES} retries: {url}"
        raise RuntimeError(msg) from last_error

    def get(self, url: str, use_cache: bool = True) -> httpx.Response:
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
        raise NotImplementedError

    async def download(
        self,
        pkg_name: str,
        version: str | None,
        output_path: Path,
        **kwargs: object,
    ) -> DownloadResult:
        raise NotImplementedError

    @abstractmethod
    def get_package_name(self, url: str) -> str | None:
        """Extract package name from URL."""

    def close(self) -> None:
        if self._session is not None:
            self._session.close()
            self._session = None

    def __del__(self) -> None:
        self.close()


import time as _time
