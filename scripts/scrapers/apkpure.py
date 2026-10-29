"""APKPure scraper implementation."""

from __future__ import annotations

from pathlib import Path

from selectolax.lexbor import LexborHTMLParser

from scripts.scrapers.base import (
    ChallengeError,
    DownloadResult,
    DownloadSource,
    ScraperBase,
    VersionInfo,
)
from scripts.scrapers.browser import ChallengeBrowser

APKPURE_BASE = "https://apkpure.net"


class APKPureScraper(ScraperBase):
    """Scraper for APKPure.net."""

    def __init__(self) -> None:
        super().__init__(DownloadSource.APKPURE)
        self._browser: ChallengeBrowser | None = None

    def _build_url(self, name: str, package: str, path: str = "") -> str:
        base = f"{APKPURE_BASE}/{name}/{package}"
        if path:
            return f"{base}/{path}"
        return base

    @staticmethod
    def _split_pkg_name(pkg_name: str) -> tuple[str, str]:
        """Split a ``name-slug/package.id`` identifier into (name, package).

        APKPure URLs need both segments (e.g.
        ``apkpure.net/sd-maid-2-se/eu.darken.sdmse``) -- callers that only
        have the raw Android package id (no slash) get it echoed back as
        both, matching the previous default-to-``pkg_name`` behavior.
        """
        if "/" in pkg_name:
            name, package = pkg_name.rsplit("/", 1)
            return name, package
        return pkg_name, pkg_name

    def _parse_versions_page(self, html_content: str) -> list[VersionInfo]:
        tree = LexborHTMLParser(html_content)
        versions: list[VersionInfo] = []
        seen: set[str] = set()
        # Current markup first (ul.version-list), then the older div.ver-item layout.
        texts = [item.attrs.get("data-dt-version") or "" for item in tree.css("ul.version-list li.version")]
        texts += [item.text(strip=True) for item in tree.css("div.ver-item a span.ver-item-n")]
        for raw in texts:
            text = raw.strip()
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
        tree = LexborHTMLParser(html_content)
        link = tree.css_first("a#download_link")
        if link is not None:
            href = link.attrs.get("href")
            if href:
                return str(href).strip()
        link = tree.css_first("a.da")
        if link is not None:
            href = link.attrs.get("href")
            if href:
                return str(href).strip()
        return None

    async def _browser_text(self, url: str) -> str:
        """Page HTML through a real browser, which clears the Cloudflare challenge plain HTTP cannot."""
        if self._browser is None:
            self._browser = ChallengeBrowser()
        return await self._browser.fetch_html(url)

    async def _close_browser(self) -> None:
        # Each DownloadManager call has its own event loop, so a browser must not outlive it.
        if self._browser is not None:
            await self._browser.aclose()
            self._browser = None

    async def _get_text(self, url: str) -> str:
        try:
            return (await self.get(url)).text
        except ChallengeError:
            return await self._browser_text(url)

    async def get_versions(self, pkg_name: str, **kwargs: object) -> list[VersionInfo]:
        default_name, package = self._split_pkg_name(pkg_name)
        name = str(kwargs.get("name", default_name))
        url = self._build_url(name, package, "versions")
        try:
            versions = self._parse_versions_page(await self._get_text(url))
            if not versions:
                # Outside CI the challenge is a 200 stub, not a 403, so it parses to nothing.
                versions = self._parse_versions_page(await self._browser_text(url))
            return versions
        finally:
            await self._close_browser()

    async def download(
        self,
        pkg_name: str,
        version: str | None,
        output_path: Path,
        **kwargs: object,
    ) -> DownloadResult:
        if version is None:
            return DownloadResult(success=False, error="Version is required")

        default_name, package = self._split_pkg_name(pkg_name)
        name = str(kwargs.get("name", default_name))
        url = self._build_url(name, package, f"download/{version}")

        try:
            download_url = self._parse_download_link(await self._get_text(url))
            if download_url is None:
                download_url = self._parse_download_link(await self._browser_text(url))
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

            await self.write(dl_response, output_path)

            return DownloadResult(success=True, file_path=output_path, version=version)

        except Exception as e:
            return DownloadResult(success=False, error=str(e))
        finally:
            await self._close_browser()
