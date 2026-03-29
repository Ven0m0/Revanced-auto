"""APKMonk scraper implementation.

Inherits from ScraperBase and provides async methods for fetching
versions and downloading APKs from APKMonk.
"""

from __future__ import annotations

import asyncio
import re
from pathlib import Path

from selectolax.parser import HTMLParser

from scripts.scrapers.base import (
    DownloadResult,
    DownloadSource,
    ScraperBase,
    VersionInfo,
)

APKMONK_BASE = "https://www.apkmonk.com"


class APKMonkScraper(ScraperBase):
    """Scraper for APKMonk.com."""

    def __init__(self) -> None:
        super().__init__(DownloadSource.APKMonk)

    def _build_url(self, package: str, path: str = "") -> str:
        """Build APKMonk URL.

        Args:
            package: Package name.
            path: Additional path suffix.

        Returns:
            Full URL path.

        """
        base = f"{APKMONK_BASE}/app/{package}"
        if path:
            return f"{base}/{path}"
        return base

    def _parse_versions_page(self, html_content: str) -> list[VersionInfo]:
        """Parse versions from APKMonk versions page.

        Args:
            html_content: HTML of the versions page.

        Returns:
            List of VersionInfo objects.

        """
        tree = HTMLParser(html_content)
        versions: list[VersionInfo] = []

        for item in tree.css("div.version-content"):
            version_elem = item.css_first("span.version")
            version = version_elem.text(strip=True) if version_elem else None
            if version:
                download_elem = item.css_first("a.download-btn")
                url = download_elem.attrs.get("href") if download_elem else None
                versions.append(VersionInfo(version=version, url=url))

        for item in tree.css("div.related-ver-content"):
            version_elem = item.css_first("span.version")
            version = version_elem.text(strip=True) if version_elem else None
            if version:
                download_elem = item.css_first("a.download-btn")
                url = download_elem.attrs.get("href") if download_elem else None
                versions.append(VersionInfo(version=version, url=url))

        return versions

    def _parse_download_link(self, html_content: str) -> str | None:
        """Extract download URL from APKMonk download page.

        Args:
            html_content: HTML of the download page.

        Returns:
            Download URL or None if not found.

        """
        tree = HTMLParser(html_content)

        download_link = tree.css_first("a.download-link")
        if download_link is not None:
            href = download_link.attrs.get("href")
            if href:
                return href.strip()

        download_btn = tree.css_first("div.download-btn a")
        if download_btn is not None:
            href = download_btn.attrs.get("href")
            if href:
                return href.strip()

        return None

    async def get_versions(self, pkg_name: str, **kwargs: object) -> list[VersionInfo]:
        """Get available versions for an app.

        Args:
            pkg_name: Package name (e.g., 'com.google.android.youtube').
            name: App name slug (passed via kwargs, unused for APKMonk).

        Returns:
            List of VersionInfo objects.

        """
        url = self._build_url(pkg_name)

        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(None, self.get, url)
        html = response.text

        return self._parse_versions_page(html)

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
            version: Version string to download.
            output_path: Path to save the APK.
            name: App name slug (passed via kwargs, unused for APKMonk).

        Returns:
            DownloadResult with success status and file path.

        """
        if version is None:
            return DownloadResult(success=False, error="Version is required")

        url = self._build_url(pkg_name, f"download/{version}")

        loop = asyncio.get_event_loop()

        try:
            response = await loop.run_in_executor(None, self.get, url)
            html = response.text

            download_url = self._parse_download_link(html)
            if download_url is None:
                return DownloadResult(success=False, error="Download link not found")

            dl_response = await loop.run_in_executor(None, self._request_with_retry, download_url, "GET")

            content_type = dl_response.headers.get("content-type", "")
            if "text/html" in content_type.lower():
                download_url = self._parse_download_link(dl_response.text)
                if download_url is None:
                    return DownloadResult(success=False, error="Download link not found")
                dl_response = await loop.run_in_executor(None, self._request_with_retry, download_url, "GET")

            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, "wb") as f:
                f.writelines(dl_response.iter_bytes(chunk_size=8192))

            return DownloadResult(
                success=True,
                file_path=output_path,
                version=version,
            )

        except Exception as e:
            return DownloadResult(success=False, error=str(e))

    def get_package_name(self, url: str) -> str | None:
        """Extract package name from APKMonk URL.

        Args:
            url: APKMonk URL in format https://www.apkmonk.com/app/{package}/.

        Returns:
            Package name if found, None otherwise.

        """
        pattern = r"apkmonk\.com/app/([a-zA-Z0-9_.]+)"
        match = re.search(pattern, url)
        if match:
            return match.group(1)
        return None
