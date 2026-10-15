"""Base scraper class and common types for all APK download sources."""

import asyncio
import contextlib
import random
import time
from abc import ABC
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

from curl_cffi import requests as curl_requests
from curl_cffi.requests.exceptions import RequestException

if TYPE_CHECKING:
    from curl_cffi.requests.session import HttpMethod

APK_ARCHIVE_URL = "https://archive.org"

# Alias so a future transport swap only touches this one line.
type Response = curl_requests.Response


class DownloadSource(Enum):
    APKMIRROR = "apkmirror"
    UPTODOWN = "uptodown"
    APKPURE = "apkpure"
    APTOIDE = "aptoide"
    ARCHIVE = "archive"
    APKMonk = "apkmonk"
    GITHUB = "github"


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
    MAX_RETRIES: int = 5
    BASE_DELAY: float = 1.0
    # Cloudflare's rate-limit challenge on apkmirror.com (429 + cf-mitigated:
    # challenge) measured live to clear after ~20s; back off from there instead
    # of the ordinary transport-error delay, or the retry budget burns inside
    # the penalty window.
    RATE_LIMIT_DELAY: float = 15.0
    CACHE_TTL: int = 3600
    # Minimum spacing between outgoing requests from one scraper instance, so
    # a burst of page fetches (e.g. resolving several release pages back to
    # back) doesn't itself trigger the rate limit.
    MIN_REQUEST_INTERVAL: float = 1.0

    def __init__(self, source: DownloadSource) -> None:
        self.source = source
        self._session: curl_requests.AsyncSession | None = None
        self._cache: dict[str, tuple[float, Response]] = {}
        self._last_request_at: float = 0.0

    async def _throttle(self) -> None:
        """Sleep just enough to keep requests at least MIN_REQUEST_INTERVAL apart."""
        elapsed = time.monotonic() - self._last_request_at
        wait = self.MIN_REQUEST_INTERVAL - elapsed
        if wait > 0:
            await asyncio.sleep(wait)
        self._last_request_at = time.monotonic()

    @property
    def session(self) -> curl_requests.AsyncSession:
        if self._session is None:
            # impersonate="chrome" matches curl-cffi's TLS/JA3 fingerprint to a
            # real Chrome build, which is what gets past Cloudflare's bot
            # check -- a plain User-Agent header does not.
            self._session = curl_requests.AsyncSession(timeout=30.0, impersonate="chrome")
        return self._session

    def _get_cache(self, key: str) -> Response | None:
        if key in self._cache:
            timestamp, value = self._cache[key]
            if timestamp + self.CACHE_TTL > time.time():
                return value
            del self._cache[key]
        return None

    def _set_cache(self, key: str, value: Response) -> None:
        self._cache[key] = (time.time(), value)

    async def _request_with_retry(
        self,
        url: str,
        method: str = "GET",
        **kwargs: Any,
    ) -> Response:
        delay = self.BASE_DELAY
        last_error: Exception | None = None

        for attempt in range(self.MAX_RETRIES):
            await self._throttle()
            try:
                response = await self.session.request(cast("HttpMethod", method), url, allow_redirects=True, **kwargs)
                if response.status_code in (429, 503) and attempt < self.MAX_RETRIES - 1:
                    await asyncio.sleep(self._rate_limit_wait(response, attempt))
                    continue
                response.raise_for_status()  # type: ignore[no-untyped-call]
            except RequestException as e:
                last_error = e
                if attempt < self.MAX_RETRIES - 1:
                    await asyncio.sleep(delay)
                    delay *= 2
            else:
                return response

        msg = f"Request failed after {self.MAX_RETRIES} retries: {url}"
        raise RuntimeError(msg) from last_error

    def _rate_limit_wait(self, response: Response, attempt: int) -> float:
        """Backoff duration for a 429/503 response: Retry-After header if present, else escalating delay."""
        retry_after: str | None = response.headers.get("retry-after") if response.headers else None
        if retry_after:
            with contextlib.suppress(ValueError):
                return float(retry_after)
        # Jitter only spreads out concurrent retries; not security-sensitive.
        return self.RATE_LIMIT_DELAY * (2.0**attempt) + random.uniform(0, 1)  # noqa: S311

    async def get(self, url: str, use_cache: bool = True) -> Response:
        """GET ``url``, retrying on failure and caching successful responses."""
        cache_key = f"get:{url}"
        if use_cache:
            cached = self._get_cache(cache_key)
            if cached is not None:
                return cached

        response = await self._request_with_retry(url)
        if use_cache:
            self._set_cache(cache_key, response)
        return response

    async def save(self, url: str, output_path: Path) -> None:
        """Fetch ``url`` and write its body to ``output_path``, creating parent dirs."""
        response = await self._request_with_retry(url)
        await self.write(response, output_path)

    async def write(self, response: Response, output_path: Path) -> None:
        """Write an already-fetched response's body to ``output_path``, creating parent dirs."""
        await asyncio.to_thread(output_path.parent.mkdir, parents=True, exist_ok=True)
        await asyncio.to_thread(output_path.write_bytes, response.content)

    async def get_versions(self, pkg_name: str) -> list[VersionInfo]:
        raise NotImplementedError

    async def download(
        self,
        pkg_name: str,
        version: str | None,
        output_path: Path,
    ) -> DownloadResult:
        raise NotImplementedError

    async def aclose(self) -> None:
        if self._session is not None:
            await self._session.close()
            self._session = None

    def close(self) -> None:
        """Sync cleanup: drop the session handle. Use ``aclose()`` from async code."""
        self._session = None

    def __del__(self) -> None:
        self._session = None
