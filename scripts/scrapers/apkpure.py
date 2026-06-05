"""APKPure scraper implementation."""

from __future__ import annotations

import asyncio
import re
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import httpx
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
        base = f"{APKPURE_BASE}/{name}/{package}"
        if path:
            return f"{base}/{path}"
        return base

    def _parse_versions_page(self, html_content: str) -> list[VersionInfo]:
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
        name = str(kwargs.get("name", pkg_name))
        url = self._build_url(name, pkg_name, "versions")
        response = await self.get(url)
        html = response.text
        return self._parse_versions_page(html)

    async def download(
        self,
        pkg_name: str,
        version: str | None,
        output_path: Path,
        **kwargs: object,
    ) -> DownloadResult:
        if version is None:
            return DownloadResult(success=False, error="Version is required")

        name = str(kwargs.get("name", pkg_name))
        url = self._build_url(name, pkg_name, f"download/{version}")

        try:
            response = await self.get(url)
            html = response.text
            download_url = self._parse_download_link(html)
            if download_url is None:
                return DownloadResult(success=False, error="Download link not found")

            dl_response = await self._request_with_retry(download_url, "GET")
            content_type = dl_response.headers.get("content-type", "")
            if "text/html" in content_type.lower():
                html = dl_response.text
                download_url = self._parse_download_link(html)
                if download_url is None:
                    return DownloadResult(success=False, error="Download link not found")
                dl_response = await self._request_with_retry(download_url, "GET")

            await asyncio.to_thread(self._save_apk, dl_response, output_path)

            return DownloadResult(success=True, file_path=output_path, version=version)

        except Exception as e:
            return DownloadResult(success=False, error=str(e))

    def _save_apk(self, response: httpx.Response, output_path: Path) -> None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open("wb") as f:
            f.writelines(response.iter_bytes(chunk_size=8192))

    def get_package_name(self, url: str) -> str | None:
        pattern = r"apkpure\.net/[^/]+/([a-zA-Z0-9_.]+)"
        match = re.search(pattern, url)
        if match:
            return match.group(1)
        return None
