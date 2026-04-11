"""Uptodown scraper module for APK version lookup and downloads."""

from __future__ import annotations

import asyncio
import contextlib
import re
import time
import zipfile
from dataclasses import dataclass
from io import BytesIO
from typing import TYPE_CHECKING

from selectolax.parser import HTMLParser

from scripts.lib import logging as log

if TYPE_CHECKING:
    from pathlib import Path

    import httpx
    from selectolax.parser import Node

from scripts.scrapers.base import (
    DownloadResult,
    DownloadSource,
    ScraperBase,
    VersionInfo,
)

SUPPORTED_ARCHS = frozenset({"arm64-v8a", "armeabi-v7a", "x86", "x86_64"})

XAPK_MIME_TYPES = frozenset(
    {
        "application/vnd.android.package-archive",
        "application/xapk",
        "application/octet-stream",
    }
)


@dataclass
class UptodownVersion:
    """Represents an Uptodown version entry.

    Attributes:
        version: Version string.
        url: Download URL.
        arch: Target architecture (None for universal).
        file_id: Uptodown file ID.
        is_xapk: Whether the file is an XAPK bundle.

    """

    version: str
    url: str | None
    arch: str | None
    file_id: str
    is_xapk: bool = False


class UptodownScraper(ScraperBase):
    """Uptodown scraper for Android APK version lookup and downloads.

    Provides async methods for fetching available versions and downloading
    specific APK versions from Uptodown's Android app repository.

    Attributes:
        source: Download source identifier (UPTODOWN).
        base_url: Base URL template for Uptodown app pages.
        max_pages: Maximum number of pages to search for versions.

    Example:
        >>> scraper = UptodownScraper()
        >>> versions = await scraper.get_versions("youtube")
        >>> result = await scraper.download("youtube", versions[0].version, Path("out.apk"))

    """

    def __init__(self) -> None:
        """Initialize Uptodown scraper."""
        super().__init__(DownloadSource.UPTODOWN)
        self.base_url = "https://{app}.en.uptodown.com/android"
        self.max_pages = 5

    def get_package_name(self, url: str) -> str | None:
        """Extract package/app name from Uptodown URL.

        Args:
            url: Uptodown URL in format https://{app}.en.uptodown.com/android

        Returns:
            App name if found, None otherwise.

        """
        pattern = r"https://([^.]+)\.en\.uptodown\.com/android"
        match = re.match(pattern, url)
        if match:
            return match.group(1)
        return None

    def _build_app_url(self, app: str) -> str:
        """Build the base app page URL.

        Args:
            app: App/package name.

        Returns:
            Full Uptodown URL for the app.

        """
        return self.base_url.format(app=app)

    def _build_version_page_url(self, app: str, page: int) -> str:
        """Build URL for a specific version page.

        Args:
            app: App/package name.
            page: Page number (1-indexed).

        Returns:
            URL for the version listing page.

        """
        base = self._build_app_url(app)
        return f"{base}/versions/page/{page}"

    async def _fetch_page(self, url: str) -> str | None:
        """Fetch a page with retry logic.

        Args:
            url: URL to fetch.

        Returns:
            Page HTML content or None if fetch failed.

        """
        try:
            response = await asyncio.to_thread(self.get, url)
        except Exception:
            return None
        else:
            return response.text

    def _parse_version_card(self, node: Node) -> UptodownVersion | None:
        """Parse a version card node to extract version info.

        Args:
            node: selectolax Node for the version card.

        Returns:
            UptodownVersion if parsing succeeded, None otherwise.

        """
        try:
            version_link = node.css_first("a.version-detail")
            if version_link is None:
                return None

            version = version_link.text(strip=True)

            href = version_link.attrs.get("href", "")
            file_id_match = re.search(r"/download/([^/]+)", href)
            file_id = file_id_match.group(1) if file_id_match else ""

            file_type = node.css_first("span.file-type")
            is_xapk = False
            if file_type:
                type_text = file_type.text(strip=True).lower()
                is_xapk = "xapk" in type_text or "bundle" in type_text

            arch_elem = node.css_first("p:last-child")
            arch: str | None = None
            if arch_elem:
                arch_text = arch_elem.text(strip=True)
                for supported in SUPPORTED_ARCHS:
                    if supported in arch_text:
                        arch = supported
                        break

            return UptodownVersion(
                version=version,
                url=href
                if href.startswith("http")
                else f"https://{self.get_package_name(self._build_app_url('')).lower()}.en.uptodown.com{href}",
                arch=arch,
                file_id=file_id,
                is_xapk=is_xapk,
            )
        except Exception:
            return None

    def _parse_versions_page(self, html: str) -> list[UptodownVersion]:
        """Parse HTML content for version entries.

        Args:
            html: HTML content of versions page.

        Returns:
            List of parsed UptodownVersion objects.

        """
        versions: list[UptodownVersion] = []
        with contextlib.suppress(Exception):
            tree = HTMLParser(html)
            cards = tree.css("div.card")
            for card in cards:
                version = self._parse_version_card(card)
                if version:
                    versions.append(version)
        return versions

    async def get_versions(self, pkg_name: str, **kwargs: object) -> list[VersionInfo]:
        """Get available versions for an app.

        Searches pages 1-5 for version listings and returns all found versions.

        Args:
            pkg_name: Package/app name for Uptodown URL.
            **kwargs: Additional arguments (arch filter if provided).

        Returns:
            List of VersionInfo objects with available versions.

        """
        target_arch: str | None = kwargs.get("arch")
        all_versions: list[UptodownVersion] = []

        for page in range(1, self.max_pages + 1):
            url = self._build_version_page_url(pkg_name, page)
            html = await self._fetch_page(url)

            if not html:
                await asyncio.sleep(0.5)
                continue

            page_versions = self._parse_versions_page(html)
            if not page_versions:
                break

            all_versions.extend(page_versions)
            await asyncio.sleep(0.3)

        if target_arch and target_arch in SUPPORTED_ARCHS:
            all_versions = [v for v in all_versions if v.arch == target_arch or v.arch is None]

        result: list[VersionInfo] = []
        seen: set[str] = set()
        for v in all_versions:
            if v.version in seen:
                continue
            seen.add(v.version)
            result.append(
                VersionInfo(
                    version=v.version,
                    url=v.url,
                    arch=v.arch,
                )
            )

        return result

    async def _resolve_target_version(
        self,
        pkg_name: str,
        version: str,
        target_arch: str | None,
    ) -> UptodownVersion | None:
        """Resolve UptodownVersion from version string and arch.

        Args:
            pkg_name: Package name.
            version: Version string.
            target_arch: Target architecture.

        Returns:
            UptodownVersion if found, None otherwise.

        """
        versions = await self.get_versions(pkg_name, arch=target_arch)
        for v_info in versions:
            if v_info.version == version and v_info.url:
                found_versions = await self._find_version_by_file_id(pkg_name, v_info.arch)
                for fv in found_versions:
                    if fv.version == version:
                        return fv
                return UptodownVersion(
                    version=version,
                    url=v_info.url,
                    arch=v_info.arch,
                    file_id="",
                    is_xapk=False,
                )
        return None

    async def download(
        self,
        pkg_name: str,
        version: str | None,
        output_path: Path,
        **kwargs: object,
    ) -> DownloadResult:
        """Download a specific version.

        Args:
            pkg_name: Package/app name.
            version: Version to download (None for latest).
            output_path: Path where APK should be saved.
            **kwargs: Additional arguments (arch preference).

        Returns:
            DownloadResult with success status and file path or error.

        """
        target_arch = kwargs.get("arch")
        if target_arch is not None:
            target_arch = str(target_arch) or None

        if version is None:
            versions = await self.get_versions(pkg_name, arch=target_arch)
            if not versions:
                return DownloadResult(
                    success=False,
                    file_path=None,
                    version=None,
                    error="No versions found",
                )
            version = versions[0].version

        target_version = await self._resolve_target_version(pkg_name, version, target_arch)

        if target_version is None or not target_version.url:
            return DownloadResult(
                success=False,
                file_path=None,
                version=version,
                error=f"Version {version} not found",
            )

        try:
            response = await asyncio.to_thread(self._request_with_retry, target_version.url)
            content = response.content

            if target_version.is_xapk:
                return await self._download_xapk(content, output_path, version)

            await asyncio.to_thread(output_path.parent.mkdir, parents=True, exist_ok=True)
            await asyncio.to_thread(output_path.write_bytes, content)

            return DownloadResult(
                success=True,
                file_path=output_path,
                version=version,
                error=None,
            )
        except Exception as e:
            log.error(f"Download failed: {e}")
            return DownloadResult(
                success=False,
                file_path=None,
                version=version,
                error=str(e),
            )

    async def _find_version_by_file_id(
        self,
        pkg_name: str,
        arch: str | None,
    ) -> list[UptodownVersion]:
        """Find all versions matching an architecture.

        Args:
            pkg_name: Package/app name.
            arch: Architecture to filter by.

        Returns:
            List of UptodownVersion objects matching the architecture.

        """
        all_versions: list[UptodownVersion] = []

        for page in range(1, self.max_pages + 1):
            url = self._build_version_page_url(pkg_name, page)
            html = await self._fetch_page(url)

            if not html:
                await asyncio.sleep(0.5)
                continue

            page_versions = self._parse_versions_page(html)
            if not page_versions:
                break

            all_versions.extend(
                v for v in page_versions if arch is None or v.arch == arch or v.arch is None
            )

            await asyncio.sleep(0.3)

        return all_versions

    async def _download_xapk(
        self,
        content: bytes,
        output_path: Path,
        version: str | None,
    ) -> DownloadResult:
        """Handle XAPK bundle download.

        XAPK files are ZIP archives containing APK files. This method extracts
        and saves the main APK.

        Args:
            content: XAPK file content.
            output_path: Path where APK should be saved.
            version: Version string for result.

        Returns:
            DownloadResult with success status.

        """
        try:
            with zipfile.ZipFile(BytesIO(content)) as zf:
                namelist = zf.namelist()
                apk_files = [n for n in namelist if n.endswith(".apk")]

                if not apk_files:
                    return DownloadResult(
                        success=False,
                        file_path=None,
                        version=version,
                        error="No APK found in XAPK bundle",
                    )

                main_apk = apk_files[0]
                apk_content = zf.read(main_apk)

                await asyncio.to_thread(output_path.parent.mkdir, parents=True, exist_ok=True)
                await asyncio.to_thread(output_path.write_bytes, apk_content)

                return DownloadResult(
                    success=True,
                    file_path=output_path,
                    version=version,
                    error=None,
                )
        except zipfile.BadZipFile:
            return DownloadResult(
                success=False,
                file_path=None,
                version=version,
                error="Invalid XAPK file format",
            )
        except Exception as e:
            return DownloadResult(
                success=False,
                file_path=None,
                version=version,
                error=f"XAPK extraction failed: {e}",
            )

    def _request_with_retry(self, url: str) -> httpx.Response:
        """Make HTTP request with retry logic.

        Args:
            url: URL to request.

        Returns:
            HTTP response.

        Raises:
            RuntimeError: If all retries fail.

        """
        delay = self.BASE_DELAY
        last_error: Exception | None = None

        for attempt in range(self.MAX_RETRIES):
            try:
                response = self.session.get(url)
                response.raise_for_status()
            except Exception as e:
                last_error = e
                if attempt < self.MAX_RETRIES - 1:
                    time.sleep(delay)
                    delay *= 2
            else:
                return response

        msg = f"Request failed after {self.MAX_RETRIES} retries: {url}"
        raise RuntimeError(msg) from last_error
