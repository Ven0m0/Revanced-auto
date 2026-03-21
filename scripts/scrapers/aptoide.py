"""Aptoide scraper implementation.

Inherits from ScraperBase and provides async methods for fetching
versions and downloading APKs from Aptoide.
"""

from __future__ import annotations

import asyncio
import re
from pathlib import Path

from scripts.scrapers.base import (
    DownloadResult,
    DownloadSource,
    ScraperBase,
    VersionInfo,
)


APTOIDE_API = "https://ws75.aptoide.com/api/7"


class AptoideScraper(ScraperBase):
    """Scraper for Aptoide."""

    ARCH_MAP = {
        "armeabi-v7a": "armeabi-v7a",
        "arm64-v8a": "arm64-v8a",
        "x86": "x86",
        "x86_64": "x86_64",
        "universal": "universal",
    }

    def __init__(self) -> None:
        super().__init__(DownloadSource.APTOIDE)

    def _build_info_url(self, package: str) -> str:
        """Build Aptoide app info URL.

        Args:
            package: Android package name.

        Returns:
            API URL for app info.

        """
        return f"{APTOIDE_API}/app/{package}/getInfo"

    def _build_versions_url(self, package: str) -> str:
        """Build Aptoide versions URL.

        Args:
            package: Android package name.

        Returns:
            API URL for versions.

        """
        return f"{APTOIDE_API}/app/{package}/getVersions"

    def _parse_version_info(self, data: dict) -> list[VersionInfo]:
        """Parse version info from Aptoide API response.

        Args:
            data: JSON response from Aptoide API.

        Returns:
            List of VersionInfo objects.

        """
        versions: list[VersionInfo] = []
        versions_list = data.get("data", {}).get("versions", [])
        for item in versions_list:
            version = item.get("version")
            if not version:
                continue
            apk_files = item.get("file", {})
            path = apk_files.get("path")
            arch = item.get("architecture")
            versions.append(VersionInfo(
                version=version,
                url=path,
                arch=arch,
            ))
        return versions

    def _filter_by_architecture(
        self,
        versions: list[VersionInfo],
        arch: str,
    ) -> list[VersionInfo]:
        """Filter versions by architecture.

        Args:
            versions: List of VersionInfo objects.
            arch: Target architecture.

        Returns:
            Filtered list of VersionInfo objects.

        """
        if arch == "universal":
            return versions
        return [v for v in versions if v.arch == arch or v.arch == "universal"]

    async def get_versions(self, pkg_name: str, **kwargs: object) -> list[VersionInfo]:
        """Get available versions for an app.

        Args:
            pkg_name: Package name (e.g., 'com.google.android.youtube').
            arch: Architecture filter (optional).

        Returns:
            List of VersionInfo objects.

        """
        url = self._build_versions_url(pkg_name)
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(None, self.get, url)
        data = response.json()
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
        """Download specific version of an app.

        Args:
            pkg_name: Package name.
            version: Version string to download.
            output_path: Path to save the APK.
            arch: Architecture filter (optional).

        Returns:
            DownloadResult with success status and file path.

        """
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

        loop = asyncio.get_event_loop()
        try:
            dl_response = await loop.run_in_executor(
                None, self._request_with_retry, target_version.url, "GET"
            )

            content_type = dl_response.headers.get("content-type", "")
            if "text/html" in content_type.lower():
                return DownloadResult(success=False, error="Received HTML instead of APK")

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
        """Extract package name from Aptoide URL.

        Args:
            url: Aptoide URL in format https://{subdomain}.aptoide.com/{package}.

        Returns:
            Package name if found, None otherwise.

        """
        pattern = r"aptoide\.com/([a-zA-Z0-9_.]+)"
        match = re.search(pattern, url)
        if match:
            pkg = match.group(1)
            if "." in pkg:
                return pkg
        return None
