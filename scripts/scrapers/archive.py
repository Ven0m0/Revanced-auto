"""Archive.org scraper for j-hc-apks collection."""

from __future__ import annotations

import asyncio
import re
from pathlib import Path
from typing import TYPE_CHECKING

from selectolax.parser import HTMLParser

from .base import APK_ARCHIVE_URL, DownloadResult, DownloadSource, ScraperBase, VersionInfo

if TYPE_CHECKING:
    from re import Match

ARCHIVE_COLLECTION = "jhc-apks"
ARCHIVE_BASE_URL = f"{APK_ARCHIVE_URL}/download/{ARCHIVE_COLLECTION}/apks"


class ArchiveScraper(ScraperBase):
    """Scraper for Archive.org j-hc-apks collection."""

    VERSION_PATTERN = re.compile(
        r"^(?P<package>[a-zA-Z0-9_.-]+?)[-_](?P<version>[0-9]+(?:\.[0-9]+)*)[-_](?P<arch>\w+)(?:\.apk)?$",
        re.IGNORECASE,
    )

    def __init__(self) -> None:
        super().__init__(DownloadSource.ARCHIVE)

    def get_package_name(self, url: str) -> str | None:
        match = re.search(r"/apks/([a-zA-Z0-9_.-]+?)(?:[-_]|$)", url)
        if match:
            return match.group(1)
        return None

    async def get_versions(self, pkg_name: str, **kwargs: object) -> list[VersionInfo]:
        url = f"{ARCHIVE_BASE_URL}/{pkg_name}"
        response = await asyncio.to_thread(self.get, url)
        parser = HTMLParser(response.text)

        versions: list[VersionInfo] = []
        seen: set[str] = set()

        for link in parser.css("a"):
            href = link.attributes.get("href", "")
            if not href or href.startswith("?") or "/" not in href:
                continue

            filename = href.rstrip("/").split("/")[-1]
            if not filename.endswith(".apk"):
                continue

            parsed = self._parse_filename(filename)
            if parsed is None:
                continue

            version_key = f"{parsed.version}-{parsed.arch}"
            if version_key in seen:
                continue
            seen.add(version_key)

            versions.append(
                VersionInfo(
                    version=parsed.version,
                    url=f"{ARCHIVE_BASE_URL}/{pkg_name}/{filename}",
                    arch=parsed.arch,
                )
            )

        versions.sort(
            key=lambda v: [int(x) if x.isdigit() else x for x in v.version.split(".")],
            reverse=True,
        )
        return versions

    def _parse_filename(self, filename: str) -> VersionInfo | None:
        name_without_ext = filename.rsplit(".apk", 1)[0]
        match: Match[str] | None = self.VERSION_PATTERN.match(name_without_ext)
        if not match:
            return None

        return VersionInfo(
            version=match.group("version"),
            arch=match.group("arch"),
        )

    async def download(
        self,
        pkg_name: str,
        version: str | None,
        output_path: Path,
        **kwargs: object,
    ) -> DownloadResult:
        arch: str | None = kwargs.get("arch")

        if version is None:
            return DownloadResult(
                success=False,
                error="Version is required for Archive.org downloads",
            )

        versions = await self.get_versions(pkg_name, **kwargs)

        for v in versions:
            if v.version == version and (arch is None or v.arch == arch):
                loop = asyncio.get_running_loop()
                return await loop.run_in_executor(
                    None,
                    self._download_file,
                    v.url,
                    output_path,
                    v.version,
                )

        return DownloadResult(
            success=False,
            error=f"Version {version} not found for package {pkg_name}",
        )

    def _download_file(
        self,
        url: str,
        output_path: Path,
        version: str,
    ) -> DownloadResult:
        try:
            response = self.session.get(url, follow_redirects=True)
            response.raise_for_status()

            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(response.content)

            return DownloadResult(
                success=True,
                file_path=output_path,
                version=version,
            )
        except Exception as e:
            return DownloadResult(
                success=False,
                error=str(e),
            )
