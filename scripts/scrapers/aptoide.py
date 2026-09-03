"""Aptoide scraper implementation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from scripts.scrapers.base import (
    DownloadResult,
    DownloadSource,
    ScraperBase,
    VersionInfo,
)

APTOIDE_API = "https://ws75.aptoide.com/api/7"


class AptoideScraper(ScraperBase):
    """Scraper for Aptoide."""

    def __init__(self) -> None:
        super().__init__(DownloadSource.APTOIDE)

    def _build_versions_url(self, package: str) -> str:
        return f"{APTOIDE_API}/app/{package}/getVersions"

    def _parse_version_info(self, data: dict[str, Any]) -> list[VersionInfo]:
        versions: list[VersionInfo] = []
        versions_list = data.get("data", {}).get("versions", [])
        for item in versions_list:
            version = item.get("version")
            if not version:
                continue
            apk_files = item.get("file", {})
            path = apk_files.get("path")
            arch = item.get("architecture")
            versions.append(VersionInfo(version=version, url=path, arch=arch))
        return versions

    def _filter_by_architecture(self, versions: list[VersionInfo], arch: str) -> list[VersionInfo]:
        if arch == "universal":
            return versions
        return [v for v in versions if v.arch == arch or v.arch == "universal"]

    async def get_versions(self, pkg_name: str, **kwargs: object) -> list[VersionInfo]:
        url = self._build_versions_url(pkg_name)
        response = await self.get(url)
        data: dict[str, Any] = json.loads(response.text)
        versions = self._parse_version_info(data)
        arch = str(kwargs.get("arch", "universal"))
        if arch and arch != "universal":
            versions = self._filter_by_architecture(versions, arch)
        return versions

    async def download(
        self,
        pkg_name: str,
        version: str | None,
        output_path: Path,
        **kwargs: object,
    ) -> DownloadResult:
        if version is None:
            return DownloadResult(success=False, error="Version is required")

        arch = str(kwargs.get("arch", "universal"))
        versions = await self.get_versions(pkg_name, arch=arch)

        target_version: VersionInfo | None = None
        for v in versions:
            if v.version == version:
                target_version = v
                break

        if target_version is None:
            return DownloadResult(success=False, error=f"Version {version} not found")
        if target_version.url is None:
            return DownloadResult(success=False, error="Download URL not available")

        try:
            dl_response = await self._request_with_retry(target_version.url, "GET")
            content_type = dl_response.headers.get("content-type", "")
            if "text/html" in content_type.lower():
                return DownloadResult(success=False, error="Received HTML instead of APK")
            await self.write(dl_response, output_path)
            return DownloadResult(success=True, file_path=output_path, version=version)
        except Exception as e:
            return DownloadResult(success=False, error=str(e))
