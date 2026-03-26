"""APKPure scraper implementation.

Inherits from ScraperBase and provides async methods for fetching
versions and downloading APKs from APKPure.
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


APKPURE_BASE = "https://apkpure.net"


class APKPureScraper(ScraperBase):
    """Scraper for APKPure.net."""

    def __init__(self) -> None:
        super().__init__(DownloadSource.APKPURE)

    def _build_url(self, name: str, package: str, path: str = "") -> str:
        """Build APKPure URL.

        Args:
            name: App name slug on APKPure.
            package: Android package name.
            path: Additional path suffix.

        Returns:
            Full URL path.

        """
        base = f"{APKPURE_BASE}/{name}/{package}"
        if path:
            return f"{base}/{path}"
        return base

    def _parse_versions_page(self, html_content: str) -> list[VersionInfo]:
        """Parse versions from APKPure versions page.

        Args:
            html_content: HTML of the versions page.

        Returns:
            List of VersionInfo objects.

        """
        tree = HTMLParser(html_content)
        versions: list[VersionInfo] = []
        seen: set[str] = set()

        for item in tree.css("div.ver-item a span.ver-item-n"):
            text = item.text(strip=True)
            if text and text not in seen:
                seen.add(text)
                versions.append(VersionInfo(version=text))

        if not versions:
            ver_top = tree.css_first("div.ver-top-down")
            if ver_top is not None:
                dt_version = ver_top.attrs.get("data-dt-version")
                if dt_version and (version := dt_version.strip()):
                    versions.append(VersionInfo(version=version))

        return versions

    def _parse_download_link(self, html_content: str) -> str | None:
        """Extract download URL from APKPure download page.

        Args:
            html_content: HTML of the download page.

        Returns:
            Download URL or None if not found.

        """
        tree = HTMLParser(html_content)

        link = tree.css_first("a#download_link")
        if link is not None:
            href = link.attrs.get("href")
            if href:
                return href.strip()

        link = tree.css_first("a.da")
        if link is not None:
            href = link.attrs.get("href")
            if href:
                return href.strip()

        return None

    async def get_versions(self, pkg_name: str, **kwargs: object) -> list[VersionInfo]:
        """Get available versions for an app.

        Args:
            pkg_name: Package name (e.g., 'com.google.android.youtube').
            name: App name slug (passed via kwargs).

        Returns:
            List of VersionInfo objects.

        """
        name = str(kwargs.get("name", pkg_name))
        url = self._build_url(name, pkg_name, "versions")

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
            name: App name slug (passed via kwargs).

        Returns:
            DownloadResult with success status and file path.

        """
        if version is None:
            return DownloadResult(success=False, error="Version is required")

        name = str(kwargs.get("name", pkg_name))
        url = self._build_url(name, pkg_name, f"download/{version}")

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
                html = dl_response.text
                download_url = self._parse_download_link(html)
                if download_url is None:
                    return DownloadResult(success=False, error="Download link not found")
                dl_response = await loop.run_in_executor(None, self._request_with_retry, download_url, "GET")

            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, "wb") as f:
                for chunk in dl_response.iter_bytes(chunk_size=8192):
                    f.write(chunk)

            return DownloadResult(
                success=True,
                file_path=output_path,
                version=version,
            )

        except Exception as e:
            return DownloadResult(success=False, error=str(e))

    def get_package_name(self, url: str) -> str | None:
        """Extract package name from APKPure URL.

        Args:
            url: APKPure URL in format https://apkpure.net/{name}/{package}.

        Returns:
            Package name if found, None otherwise.

        """
        pattern = r"apkpure\.net/[^/]+/([a-zA-Z0-9_.]+)"
        match = re.search(pattern, url)
        if match:
            return match.group(1)
        return None
