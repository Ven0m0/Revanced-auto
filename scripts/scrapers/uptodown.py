#!/usr/bin/env python3
"""Uptodown scraper module for APK version lookup and downloads."""

from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from selectolax.parser import HTMLParser

from scripts.scrapers.base import DownloadResult, ScraperBase, VersionInfo

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
        from scripts.scrapers.base import DownloadSource

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
            response = self._request_with_retry(url)
            return response.text
        except Exception:
            return None

    def _parse_version_card(self, node: Any) -> UptodownVersion | None:
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
        try:
            tree = HTMLParser(html)
            cards = tree.css("div.card")
            for card in cards:
                version = self._parse_version_card(card)
                if version:
                    versions.append(version)
        except Exception:
            pass
        return versions

    async def get_versions(self, pkg_name: str, **kwargs: Any) -> list[VersionInfo]:
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

    async def download(
        self,
        pkg_name: str,
        version: str | None,
        output_path: Path,
        **kwargs: Any,
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
        target_arch: str | None = kwargs.get("arch")

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

        versions = await self.get_versions(pkg_name, arch=target_arch)
        target_version: UptodownVersion | None = None

        for v_info in versions:
            if v_info.version == version:
                url = v_info.url
                if url:
                    found_versions = await self._find_version_by_file_id(pkg_name, v_info.arch)
                    for fv in found_versions:
                        if fv.version == version:
                            target_version = fv
                            break
                    if target_version is None:
                        target_version = UptodownVersion(
                            version=version,
                            url=url,
                            arch=v_info.arch,
                            file_id="",
                            is_xapk=False,
                        )
                break

        if target_version is None or not target_version.url:
            return DownloadResult(
                success=False,
                file_path=None,
                version=version,
                error=f"Version {version} not found",
            )

        try:
            response = self._request_with_retry(target_version.url)
            content = response.content

            if target_version.is_xapk:
                return await self._download_xapk(content, output_path, version)

            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                self._save_apk,
                content,
                output_path,
            )

            return DownloadResult(
                success=True,
                file_path=output_path,
                version=version,
                error=None,
            )
        except Exception as e:
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

            for v in page_versions:
                if arch is None or v.arch == arch or v.arch is None:
                    all_versions.append(v)

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
        import zipfile
        from io import BytesIO

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
                loop = asyncio.get_event_loop()
                apk_content = await loop.run_in_executor(None, zf.read, main_apk)

                await loop.run_in_executor(
                    None,
                    self._save_apk,
                    apk_content,
                    output_path,
                )

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

    def _save_apk(self, content: bytes, output_path: Path) -> None:
        """Save APK content to file.

        Args:
            content: APK file content.
            output_path: Path to save the APK.

        """
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(content)

    def _request_with_retry(self, url: str) -> httpx.Response:
        """Make HTTP request with retry logic.

        Args:
            url: URL to request.

        Returns:
            HTTP response.

        Raises:
            RuntimeError: If all retries fail.

        """
        import time

        delay = self.BASE_DELAY
        last_error: Exception | None = None

        for attempt in range(self.MAX_RETRIES):
            try:
                response = self.session.get(url)
                response.raise_for_status()
                return response
            except Exception as e:
                last_error = e
                if attempt < self.MAX_RETRIES - 1:
                    time.sleep(delay)
                    delay *= 2

        msg = f"Request failed after {self.MAX_RETRIES} retries: {url}"
        raise RuntimeError(msg) from last_error
