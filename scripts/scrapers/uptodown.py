"""Uptodown scraper module for APK version lookup and downloads."""

from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING

from scripts.lib import logging as log

if TYPE_CHECKING:
    from pathlib import Path

from scripts.scrapers.base import (
    DownloadResult,
    DownloadSource,
    ScraperBase,
    VersionInfo,
)
from scripts.scrapers.browser import ChallengeBrowser

_APP_CODE_RE = re.compile(r'data-code="(\d+)"')


class UptodownScraper(ScraperBase):
    """Uptodown scraper for Android APK version lookup and downloads."""

    def __init__(self) -> None:
        super().__init__(DownloadSource.UPTODOWN)
        self.base_url = "https://{app}.en.uptodown.com/android"
        self.max_pages = 5

    def _build_app_url(self, app: str) -> str:
        return self.base_url.format(app=app)

    async def _fetch_text(self, url: str) -> str | None:
        try:
            response = await self.get(url)
        except Exception as e:
            log.warn(f"Uptodown request failed: {e}")
            return None
        return response.text

    async def get_versions(self, pkg_name: str, **kwargs: object) -> list[VersionInfo]:
        """List versions newest-first, via the JSON endpoint the site's own "see more" button uses.

        The versions page is server-rendered only for the first 20 entries and no
        longer has numbered pages; the rest come from ``/apps/<app code>/versions/<page>``.
        """
        app_url = self._build_app_url(pkg_name)
        html = await self._fetch_text(f"{app_url}/versions")
        code_match = _APP_CODE_RE.search(html or "")
        if code_match is None:
            return []
        result: list[VersionInfo] = []
        seen: set[str] = set()
        for page in range(1, self.max_pages + 1):
            body = await self._fetch_text(f"{app_url}/apps/{code_match.group(1)}/versions/{page}")
            if not body:
                break
            try:
                rows = json.loads(body).get("data") or []
            except ValueError, AttributeError:
                break
            if not rows:
                break
            for row in rows:
                version = str(row.get("version", ""))
                link = row.get("versionURL") or {}
                if not version or version in seen:
                    continue
                seen.add(version)
                # The page that hosts the download button; its file id is the link's last segment.
                url = f"{link.get('url')}/{link.get('extraURL')}/{link.get('versionID')}"
                result.append(VersionInfo(version=version, url=url))
        return result

    async def download(
        self,
        pkg_name: str,
        version: str | None,
        output_path: Path,
        **kwargs: object,
    ) -> DownloadResult:
        versions = await self.get_versions(pkg_name)
        if version is None:
            if not versions:
                return DownloadResult(success=False, file_path=None, version=None, error="No versions found")
            version = versions[0].version

        page_url = next((v.url for v in versions if v.version == version), None)
        if not page_url:
            return DownloadResult(success=False, file_path=None, version=version, error=f"Version {version} not found")

        # The download button needs a Cloudflare Turnstile token, which only a real browser can obtain.
        browser = ChallengeBrowser()
        try:
            file_url = await browser.capture_download_url(page_url, "#detail-download-button")
            await self.save(file_url, output_path)
        except Exception as e:
            log.error(f"Download failed: {e}")
            return DownloadResult(success=False, file_path=None, version=version, error=str(e))
        finally:
            await browser.aclose()
        return DownloadResult(success=True, file_path=output_path, version=version, error=None)
