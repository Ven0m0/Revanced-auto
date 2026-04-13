#!/usr/bin/env python3
"""Network utilities module for HTTP requests with retry logic."""

from __future__ import annotations

import asyncio
import fcntl
import hashlib
import os
import sys
import time
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, ClassVar

import httpx

if TYPE_CHECKING:
    from collections.abc import Callable

DEFAULT_TIMEOUT = 300
DEFAULT_MAX_RETRIES = 4
DEFAULT_INITIAL_DELAY = 2


@dataclass
class HttpClientConfig:
    """Configuration for HTTP client.

    Attributes:
        timeout: Request timeout in seconds.
        max_retries: Maximum number of retry attempts.
        initial_delay: Initial retry delay in seconds.
        connect_timeout: Connection timeout in seconds.
        user_agent: User agent string for requests.
        github_token: GitHub API token.
        cookie_file: Path to cookie file.

    """

    timeout: int = DEFAULT_TIMEOUT
    max_retries: int = DEFAULT_MAX_RETRIES
    initial_delay: int = DEFAULT_INITIAL_DELAY
    connect_timeout: int = 10
    user_agent: str = "Mozilla/5.0 (X11; Linux x86_64; rv:142.0) Gecko/20100101 Firefox/142.0"
    github_token: str | None = field(default_factory=lambda: os.environ.get("GITHUB_TOKEN"))
    cookie_file: Path | None = None


class HttpClient:
    """Async/sync HTTP client with retry logic and file locking.

    Provides methods for making HTTP requests with automatic retry logic,
    exponential backoff, and concurrent download protection via file locking.

    Attributes:
        CONFIG: Default configuration class variable.

    Example:
        >>> client = HttpClient()
        >>> response = client.req("https://example.com", "output.txt")
        >>> async def main():
        ...     async with HttpClient() as client:
        ...         data = await client.async_get("https://api.example.com")

    """

    CONFIG: ClassVar[type[HttpClientConfig]] = HttpClientConfig

    def __init__(self, config: HttpClientConfig | None = None) -> None:
        """Initialize HTTP client with optional configuration.

        Args:
            config: Optional configuration object. Uses default if None.

        """
        self.config = config or self.CONFIG()
        self._sync_client = httpx.Client(
            timeout=httpx.Timeout(self.config.timeout),
            headers={"User-Agent": self.config.user_agent},
            follow_redirects=True,
        )
        self._async_client: httpx.AsyncClient | None = None

    def __enter__(self) -> HttpClient:
        """Enter context manager for sync client."""
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Exit context manager and close clients."""
        self._sync_client.close()
        if self._async_client:
            pass

    async def __aenter__(self) -> HttpClient:
        """Enter async context manager."""
        self._async_client = httpx.AsyncClient(
            timeout=httpx.Timeout(self.config.timeout),
            headers={"User-Agent": self.config.user_agent},
            follow_redirects=True,
        )
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Exit async context manager and close clients."""
        if self._async_client:
            await self._async_client.aclose()
        self._sync_client.close()

    def _get_cookie_header(self) -> dict[str, str]:
        """Load cookies from cookie file if configured."""
        if not self.config.cookie_file or not self.config.cookie_file.exists():
            return {}
        cookies = {}
        try:
            content = self.config.cookie_file.read_text()
            for line in content.splitlines():
                if line.startswith("#") or not line.strip():
                    continue
                parts = line.split("\t")
                if len(parts) >= 7:
                    cookies[parts[5]] = parts[6]
        except OSError:
            pass
        return cookies

    def _build_headers(self, extra_headers: dict[str, str] | None = None) -> dict[str, str]:
        """Build headers dictionary with cookies and extra headers."""
        headers = self._get_cookie_header()
        if extra_headers:
            headers.update(extra_headers)
        return headers

    def _retry_with_backoff(
        self,
        func: Callable[..., Any],
        *args: Any,
        **kwargs: Any,
    ) -> httpx.Response:
        """Execute request with retry logic and exponential backoff.

        Args:
            func: Request function to execute.
            *args: Positional arguments for the function.
            **kwargs: Keyword arguments for the function.

        Returns:
            Response object from successful request.

        Raises:
            httpx.HTTPError: If all retry attempts fail.

        """
        delay = self.config.initial_delay
        last_exception: Exception | None = None

        for attempt in range(self.config.max_retries + 1):
            try:
                return func(*args, **kwargs)
            except httpx.HTTPError as e:
                last_exception = e
                if attempt < self.config.max_retries:
                    time.sleep(delay)
                    delay *= 2
                else:
                    break

        if last_exception:
            raise last_exception
        raise httpx.HTTPError("Request failed after retries")

    async def _async_retry_with_backoff(
        self,
        func: Callable[..., Any],
        *args: Any,
        **kwargs: Any,
    ) -> httpx.Response:
        """Execute async request with retry logic and exponential backoff.

        Args:
            func: Async request function to execute.
            *args: Positional arguments for the function.
            **kwargs: Keyword arguments for the function.

        Returns:
            Response object from successful request.

        Raises:
            httpx.HTTPError: If all retry attempts fail.

        """
        delay = self.config.initial_delay
        last_exception: Exception | None = None

        for attempt in range(self.config.max_retries + 1):
            try:
                return await func(*args, **kwargs)
            except httpx.HTTPError as e:
                last_exception = e
                if attempt < self.config.max_retries:
                    await asyncio.sleep(delay)
                    delay *= 2
                else:
                    break

        if last_exception:
            raise last_exception
        raise httpx.HTTPError("Request failed after retries")

    def _do_request(
        self,
        method: str,
        url: str,
        output: str | Path | None = None,
        headers: dict[str, str] | None = None,
        **kwargs: Any,
    ) -> str | bytes:
        """Execute HTTP request with retry logic.

        Args:
            method: HTTP method (GET, POST, etc.).
            url: Request URL.
            output: Output file path or None for response content.
            headers: Additional headers for the request.
            **kwargs: Additional arguments for httpx request.

        Returns:
            Response content as string if output is None or "-",
            otherwise empty string.

        """
        full_headers = self._build_headers(headers)

        def request_func() -> httpx.Response:
            return self._sync_client.request(method, url, headers=full_headers, **kwargs)

        response = self._retry_with_backoff(request_func)

        if output == "-" or output is None:
            return response.text

        output_path = Path(output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(response.content)
        return ""

    async def _async_do_request(
        self,
        method: str,
        url: str,
        output: str | Path | None = None,
        headers: dict[str, str] | None = None,
        **kwargs: Any,
    ) -> str | bytes:
        """Execute async HTTP request with retry logic.

        Args:
            method: HTTP method (GET, POST, etc.).
            url: Request URL.
            output: Output file path or None for response content.
            headers: Additional headers for the request.
            **kwargs: Additional arguments for httpx request.

        Returns:
            Response content as string if output is None or "-",
            otherwise empty string.

        """
        if not self._async_client:
            raise RuntimeError("Async client not initialized. Use 'async with' context.")
        client = self._async_client

        full_headers = self._build_headers(headers)

        async def request_func() -> httpx.Response:
            return await client.request(method, url, headers=full_headers, **kwargs)

        response = await self._async_retry_with_backoff(request_func)

        if output == "-" or output is None:
            return response.text

        output_path = Path(output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(response.content)
        return ""

    def get(self, url: str, output: str | Path | None = None, **kwargs: Any) -> str | bytes:
        """Perform GET request.

        Args:
            url: Request URL.
            output: Output file path, "-" for stdout, or None to return content.
            **kwargs: Additional arguments for httpx request.

        Returns:
            Response content as string if output is None or "-",
            otherwise empty string.

        """
        return self._do_request("GET", url, output, **kwargs)

    def post(self, url: str, output: str | Path | None = None, **kwargs: Any) -> str | bytes:
        """Perform POST request.

        Args:
            url: Request URL.
            output: Output file path, "-" for stdout, or None to return content.
            **kwargs: Additional arguments for httpx request.

        Returns:
            Response content as string if output is None or "-",
            otherwise empty string.

        """
        return self._do_request("POST", url, output, **kwargs)

    def put(self, url: str, output: str | Path | None = None, **kwargs: Any) -> str | bytes:
        """Perform PUT request.

        Args:
            url: Request URL.
            output: Output file path, "-" for stdout, or None to return content.
            **kwargs: Additional arguments for httpx request.

        Returns:
            Response content as string if output is None or "-",
            otherwise empty string.

        """
        return self._do_request("PUT", url, output, **kwargs)

    def delete(self, url: str, output: str | Path | None = None, **kwargs: Any) -> str | bytes:
        """Perform DELETE request.

        Args:
            url: Request URL.
            output: Output file path, "-" for stdout, or None to return content.
            **kwargs: Additional arguments for httpx request.

        Returns:
            Response content as string if output is None or "-",
            otherwise empty string.

        """
        return self._do_request("DELETE", url, output, **kwargs)

    async def async_get(self, url: str, output: str | Path | None = None, **kwargs: Any) -> str | bytes:
        """Perform async GET request.

        Args:
            url: Request URL.
            output: Output file path, "-" for stdout, or None to return content.
            **kwargs: Additional arguments for httpx request.

        Returns:
            Response content as string if output is None or "-",
            otherwise empty string.

        """
        return await self._async_do_request("GET", url, output, **kwargs)

    async def async_post(self, url: str, output: str | Path | None = None, **kwargs: Any) -> str | bytes:
        """Perform async POST request.

        Args:
            url: Request URL.
            output: Output file path, "-" for stdout, or None to return content.
            **kwargs: Additional arguments for httpx request.

        Returns:
            Response content as string if output is None or "-",
            otherwise empty string.

        """
        return await self._async_do_request("POST", url, output, **kwargs)

    def close(self) -> None:
        """Close the HTTP client and release resources."""
        self._sync_client.close()
        if self._async_client:
            import asyncio

            asyncio.get_event_loop().run_until_complete(self._async_client.aclose())


def _get_deterministic_temp_path(temp_dir: Path, output_path: str | Path) -> Path:
    """Generate deterministic temp path based on output path hash.

    Args:
        temp_dir: Temporary directory.
        output_path: Target output path.

    Returns:
        Path to temporary file for the download.

    """
    path_hash = hashlib.sha256(str(output_path).encode()).hexdigest()[:32]
    return temp_dir / f"tmp.{path_hash}"


def download_with_lock(
    url: str,
    output: str | Path,
    temp_dir: str | Path | None = None,
    config: HttpClientConfig | None = None,
    headers: dict[str, str] | None = None,
) -> bool:
    """Download file with concurrent download protection via file locking.

    Uses deterministic temp paths and flock to serialize concurrent downloads
    of the same file. Only one process will download, others wait and reuse.

    Args:
        url: URL to download from.
        output: Output file path.
        temp_dir: Temporary directory for lock files and partial downloads.
        config: Optional HTTP client configuration.
        headers: Additional headers for the request.

    Returns:
        True if download succeeded or file already exists, False otherwise.

    """
    import tempfile

    output_path = Path(output).resolve()
    temp_path = _get_deterministic_temp_path(
        Path(temp_dir) if temp_dir else Path(tempfile.gettempdir()),
        output_path,
    )
    lock_file = Path(f"{temp_path}.lock")
    temp_dir_path = temp_path.parent
    temp_dir_path.mkdir(parents=True, exist_ok=True)
    temp_dir_path.chmod(0o700)

    if output_path.exists():
        return True

    lock_fd = None
    try:
        lock_fd = open(lock_file, "w")
        fcntl.flock(lock_fd.fileno(), fcntl.LOCK_EX)

        if output_path.exists():
            return True

        client = HttpClient(config)
        try:
            client.get(url, temp_path, headers=headers or {})
            temp_path.replace(output_path)
            return True
        finally:
            client.close()
    except OSError:
        return False
    except Exception:
        if temp_path.exists():
            temp_path.unlink()
        return False
    finally:
        if lock_fd:
            fcntl.flock(lock_fd.fileno(), fcntl.LOCK_UN)
            lock_fd.close()
        if lock_file.exists():
            lock_file.unlink()


async def async_download_with_lock(
    url: str,
    output: str | Path,
    temp_dir: str | Path | None = None,
    config: HttpClientConfig | None = None,
    headers: dict[str, str] | None = None,
) -> bool:
    """Async download file with concurrent download protection via file locking.

    Args:
        url: URL to download from.
        output: Output file path.
        temp_dir: Temporary directory for lock files and partial downloads.
        config: Optional HTTP client configuration.
        headers: Additional headers for the request.

    Returns:
        True if download succeeded or file already exists, False otherwise.

    """
    import tempfile

    output_path = Path(output).resolve()
    temp_path = _get_deterministic_temp_path(
        Path(temp_dir) if temp_dir else Path(tempfile.gettempdir()),
        output_path,
    )
    lock_file = Path(f"{temp_path}.lock")
    temp_dir_path = temp_path.parent
    temp_dir_path.mkdir(parents=True, exist_ok=True)
    temp_dir_path.chmod(0o700)

    if output_path.exists():
        return True

    lock_fd = None
    try:
        lock_fd = open(lock_file, "w")
        fcntl.flock(lock_fd.fileno(), fcntl.LOCK_EX)

        if output_path.exists():
            return True

        async with HttpClient(config) as client:
            await client.async_get(url, temp_path, headers=headers or {})
            temp_path.replace(output_path)
            return True
    except OSError:
        return False
    except Exception:
        if temp_path.exists():
            temp_path.unlink()
        return False
    finally:
        if lock_fd:
            fcntl.flock(lock_fd.fileno(), fcntl.LOCK_UN)
            lock_fd.close()
        if lock_file.exists():
            lock_file.unlink()


def req(
    url: str,
    output: str | Path | None = None,
    config: HttpClientConfig | None = None,
) -> str | bytes:
    """Make HTTP request with retries and default user agent.

    Args:
        url: Request URL.
        output: Output file path, "-" for stdout, or None to return content.
        config: Optional HTTP client configuration.

    Returns:
        Response content as string if output is None or "-",
        otherwise empty string.

    """
    cfg = config or HttpClientConfig()
    client = HttpClient(cfg)
    try:
        return client.get(url, output)
    finally:
        client.close()


def gh_req(
    url: str,
    output: str | Path | None = None,
    config: HttpClientConfig | None = None,
) -> str | bytes:
    """Make GitHub API request with retries.

    Uses GITHUB_TOKEN from environment or config for authentication.

    Args:
        url: GitHub API URL.
        output: Output file path, "-" for stdout, or None to return content.
        config: Optional HTTP client configuration.

    Returns:
        Response content as string if output is None or "-",
        otherwise empty string.

    """
    cfg = config or HttpClientConfig()
    token = cfg.github_token or os.environ.get("GITHUB_TOKEN")
    headers = {"Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    client = HttpClient(cfg)
    try:
        return client.get(url, output, headers=headers)
    finally:
        client.close()


def gh_dl(
    asset_path: str | Path,
    url: str,
    config: HttpClientConfig | None = None,
) -> bool:
    """Download GitHub release asset with file locking.

    Args:
        asset_path: Path where the asset should be saved.
        url: GitHub asset download URL.
        config: Optional HTTP client configuration.

    Returns:
        True if download succeeded or file already exists, False otherwise.

    """
    cfg = config or HttpClientConfig()
    token = cfg.github_token or os.environ.get("GITHUB_TOKEN")
    headers = {"Accept": "application/octet-stream"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    return download_with_lock(url, asset_path, config=cfg, headers=headers)


def _executor_download_with_lock(
    url: str,
    output: str | Path,
    temp_dir: str | Path | None = None,
    config: HttpClientConfig | None = None,
    headers: dict[str, str] | None = None,
) -> Future[bool]:
    """Submit download_with_lock to thread pool for concurrent execution.

    Args:
        url: URL to download from.
        output: Output file path.
        temp_dir: Temporary directory for lock files and partial downloads.
        config: Optional HTTP client configuration.
        headers: Additional headers for the request.

    Returns:
        Future that resolves to True if download succeeded.

    """
    executor = ThreadPoolExecutor(max_workers=1)
    return executor.submit(
        download_with_lock,
        url,
        output,
        temp_dir,
        config,
        headers,
    )


def aria2c_download(
    urls: list[str],
    output_path: str | Path,
    *,
    max_connections: int = 16,
    split: int = 16,
    min_split_size: str = "1M",
    extra_args: list[str] | None = None,
) -> bool:
    """Download a file using aria2c for multi-connection acceleration.

    Args:
        urls: List of URLs to download (mirrors).
        output_path: Destination file path.
        max_connections: Maximum concurrent connections per server.
        split: Number of chunks to split the download into.
        min_split_size: Minimum segment size for splitting.
        extra_args: Additional aria2c CLI arguments.

    Returns:
        True if download succeeded, False otherwise.

    """
    import shutil
    import subprocess

    if not shutil.which("aria2c"):
        return False

    output_path = Path(output_path)
    cmd = [
        "aria2c",
        f"--max-connection-per-server={max_connections}",
        f"--split={split}",
        f"--min-split-size={min_split_size}",
        "--dir",
        str(output_path.parent),
        "--out",
        output_path.name,
    ]
    if extra_args:
        cmd.extend(extra_args)
    cmd.extend(urls)

    try:
        subprocess.run(cmd, check=True, capture_output=True)
        return True
    except (subprocess.CalledProcessError, OSError):
        return False


def download_with_aria2c_fallback(
    urls: list[str],
    output_path: str | Path,
    *,
    config: HttpClientConfig | None = None,
    headers: dict[str, str] | None = None,
    max_connections: int = 16,
) -> bool:
    """Download a file using aria2c if available, falling back to httpx.

    Args:
        urls: List of URLs to download (first URL used for httpx fallback).
        output_path: Destination file path.
        config: Optional HTTP client configuration for fallback.
        headers: Optional headers for fallback download.
        max_connections: Max connections for aria2c.

    Returns:
        True if download succeeded, False otherwise.

    """
    import shutil

    output_path = Path(output_path)
    if shutil.which("aria2c") and aria2c_download(urls, output_path, max_connections=max_connections):
        return True

    # Fallback to httpx via download_with_lock
    primary_url = urls[0] if urls else ""
    return download_with_lock(primary_url, output_path, config=config, headers=headers)


def main() -> int:
    """Main entry point for network utilities CLI."""
    print("Network utilities module - use as library")
    return 0


if __name__ == "__main__":
    sys.exit(main())
