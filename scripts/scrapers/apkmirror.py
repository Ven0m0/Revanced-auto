"""APKMirror scraper module for APK version retrieval and downloads."""

from __future__ import annotations

import asyncio
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from selectolax.parser import HTMLParser, Node

from scripts.scrapers.base import (
    DownloadResult,
    DownloadSource,
    ScraperBase,
    VersionInfo,
)
from scripts.utils.java import JAVA_ARGS

type ArchType = Literal["universal", "noarch", "arm64-v8a", "armeabi-v7a", "arm64-v8a + armeabi-v7a"]
type BundleType = Literal["APK", "BUNDLE"]


@dataclass(frozen=True, slots=True)
class SearchConfig:
    apk_bundle: BundleType
    arch: ArchType
    exclude_alpha_beta: bool = True
    match_any: bool = False
    """Accept the first variant row for the target arch, skipping bundle preference.

    Modern releases increasingly ship only arch-split BUNDLE variants with
    dpi *ranges* (e.g. "120-480dpi") rather than a "universal"/"nodpi" row,
    so exact SearchConfig equality can match nothing even though the release
    has installable variants. Callers that only need *a* variant to exist
    (confirming a version is real, not picking a specific download) should
    set this instead of guessing bundle/arch values.
    """


@dataclass(frozen=True, slots=True)
class RowData:
    version: str
    size: str
    bundle: str
    arch: str
    dpi: str


_MIN_ROW_CELLS: int = 4


def get_target_archs(arch: ArchType) -> list[str]:
    base_archs: list[str] = ["universal", "noarch", "arm64-v8a + armeabi-v7a"]
    match arch:
        case "all":
            return base_archs
        case _:
            return [arch, *base_archs]


def _parse_row_data(row: Node) -> RowData | None:
    """Extract variant fields from a real variant table row.

    Cells are ``[version+badges, arch, min-Android-version, dpi]`` -- APKMirror
    dropped the separate "download" cell that used to make this 5 cells. The
    version cell packs several nested elements (a version link, a bundle
    type badge, a signature badge, an upload timestamp) -- flattening all
    text nodes in DOM order (the previous approach) interleaves these and
    breaks positional field mapping. Reading each field from its own cell
    (and the version from its link's own text, not the cell's) is exact.

    Returns ``None`` for the table's own header row too: it matches the same
    ``div.table-row.headerFont`` selector as real variant rows and now also
    has 4 cells, but its first cell has no ``<a>``.
    """
    cells = row.css(".table-cell")
    if len(cells) < _MIN_ROW_CELLS:
        return None
    version_link = cells[0].css_first("a")
    if version_link is None:
        return None
    version = version_link.text(strip=True)
    bundle_badge = cells[0].css_first(".apkm-badge")
    bundle = bundle_badge.text(strip=True) if bundle_badge else ""
    return RowData(
        version=version,
        size="",
        bundle=bundle,
        arch=cells[1].text(strip=True),
        dpi=cells[3].text(strip=True),
    )


def _is_prerelease(display_text: str, version_match: re.Match[str]) -> bool:
    """True if "alpha"/"beta" appears after the version number, not before it.

    APKMirror bakes a real prerelease marker into the release title as a
    suffix after the version (e.g. "21.34.248 beta"), while an app whose own
    product name contains "Beta" as a channel/brand name (e.g. "Brave Beta
    1.95.96", which lists only that channel's releases -- APKMirror never
    mixes channels within one app's release list) puts the word before the
    version. Checking only the text after the version avoids rejecting every
    release of a "*Beta" branded app.
    """
    suffix = display_text[version_match.end() :].lower()
    return "alpha" in suffix or "beta" in suffix


_BUNDLE_RANK: dict[str, int] = {"APK": 0, "BUNDLE": 1}


def _row_rank(row_data: RowData, config: SearchConfig, target_archs: list[str]) -> int | None:
    """Rank a variant row for ``config``, lower is better; ``None`` if it doesn't qualify.

    Arch is a hard filter. Bundle type is a preference (plain APK over a
    split BUNDLE, which still works via ``merge_apkm_splits``), not a
    requirement -- modern releases increasingly ship BUNDLE-only. DPI is not
    matched: the build pipeline never requests a specific one, and releases
    now carry ranges (e.g. "120-480dpi") instead of a plain "nodpi" row.
    """
    if row_data.arch not in target_archs:
        return None
    if config.match_any:
        return 0
    return _BUNDLE_RANK.get(row_data.bundle, len(_BUNDLE_RANK))


def _extract_download_url(row: Node) -> str | None:
    link = row.css_first("div > a")
    if link is None:
        return None
    href = link.attrs.get("href")
    if not href:
        return None
    return f"https://www.apkmirror.com{href}"


def _parse_rows(tree: HTMLParser) -> list[Node]:
    return tree.css("div.table-row.headerFont")


def is_apk_bundle(file_path: Path) -> bool:
    return file_path.suffix.lower() in (".apkm", ".xapk")


def merge_apkm_splits(temp_dir: Path, bundle_path: Path, output_path: Path) -> bool:
    """Merge an APKM/XAPK bundle's per-arch splits into one installable APK.

    Shared by any scraper that hands back a split bundle (APKMirror, GitHub
    releases) so there is one APKEditor-based merger, not one per scraper.
    """
    from scripts.utils.network import gh_dl

    apkeditor_jar = temp_dir / "apkeditor.jar"
    if not gh_dl(
        apkeditor_jar,
        "https://github.com/REAndroid/APKEditor/releases/download/V1.4.2/APKEditor-1.4.2.jar",
        sha256="706297058a52862d53603403337f400782782e4f0163353e4142f9a76785265a",
    ):
        msg = "Failed to download or verify APKEditor.jar"
        raise RuntimeError(msg)

    try:
        subprocess.run(
            [
                "java",
                *JAVA_ARGS,
                "-jar",
                str(apkeditor_jar),
                "merge",
                "-i",
                str(bundle_path),
                "-o",
                f"{bundle_path}.mzip",
                "-clean-meta",
                "-f",
            ],
            capture_output=True,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"APKEditor failed: {e.stderr}") from e

    extract_dir = bundle_path.with_suffix("")
    extract_dir.mkdir(exist_ok=True)
    subprocess.run(["unzip", "-qo", f"{bundle_path}.mzip", "-d", str(extract_dir)], check=True)
    zip_path = bundle_path.with_suffix(".zip")
    subprocess.run(["zip", "-0rq", str(zip_path), "."], cwd=extract_dir, check=True)
    shutil.move(str(zip_path), str(output_path))
    for cleanup in (extract_dir, bundle_path.with_suffix(".mzip")):
        shutil.rmtree(cleanup, ignore_errors=True)
    return True


class APKMirror(ScraperBase):
    BASE_URL = "https://www.apkmirror.com"
    APK_ARCH_PATH = BASE_URL + "/apk"

    def __init__(self) -> None:
        super().__init__(DownloadSource.APKMIRROR)
        self._temp_dir: Path | None = None

    @property
    def temp_dir(self) -> Path:
        if self._temp_dir is None:
            import tempfile

            self._temp_dir = Path(tempfile.mkdtemp(prefix="apkmirror_"))
        return self._temp_dir

    def _get_versions_page_url(self, pkg_name: str) -> str:
        return f"{self.APK_ARCH_PATH}/{pkg_name}/"

    def _search_variant(self, html_content: str, config: SearchConfig) -> str | None:
        tree = HTMLParser(html_content)
        rows = _parse_rows(tree)
        if not rows:
            return None
        target_archs = get_target_archs(config.arch)
        best_rank: int | None = None
        best_url: str | None = None
        for row in rows:
            row_data = _parse_row_data(row)
            if row_data is None:
                continue
            if config.exclude_alpha_beta and (
                "alpha" in row_data.version.lower() or "beta" in row_data.version.lower()
            ):
                continue
            rank = _row_rank(row_data, config, target_archs)
            if rank is None or (best_rank is not None and rank >= best_rank):
                continue
            url = _extract_download_url(row)
            if url is None:
                continue
            best_rank, best_url = rank, url
            if rank == 0:
                break
        return best_url

    def _find_download_link(self, variant_page_html: str) -> str | None:
        # Real class is "accent_bg btn btn-flat downloadButton sSo" -- the
        # site markup drifted from the "download-btn" class this used to
        # match. This link goes to a confirm/key page, not the final file.
        tree = HTMLParser(variant_page_html)
        download_btn = tree.css_first("a.downloadButton")
        if download_btn is None:
            return None
        href = download_btn.attrs.get("href")
        if not href:
            return None
        return f"{self.BASE_URL}{href}"

    def _find_final_download_link(self, confirm_page_html: str) -> str | None:
        """Extract the real download URL from a variant's confirm/key page.

        The confirm page (``.../download/?key=...``) is itself not the file
        -- it has an ``id="download-link"`` anchor pointing at
        ``/wp-content/themes/APKMirror/download.php?id=...&key=...``, which
        redirects (via a signed Cloudflare R2 URL) to the actual APK/APKM
        bytes. The session follows that redirect automatically when downloading.
        """
        tree = HTMLParser(confirm_page_html)
        link = tree.css_first("a#download-link")
        if link is None:
            return None
        href = link.attrs.get("href")
        if not href:
            return None
        return f"{self.BASE_URL}{href}"

    async def _get_download_url(self, variant_url: str) -> str | None:
        response = await self.get(variant_url)
        confirm_url = self._find_download_link(response.text)
        if confirm_url is None:
            return None
        confirm_response = await self.get(confirm_url, use_cache=False)
        return self._find_final_download_link(confirm_response.text)

    async def _list_release_pages(self, pkg_name: str) -> list[tuple[str, str]]:
        """List an app's releases newest-first as (version_text, release_url) pairs.

        Replaces the old ``div.version-fed-list`` sidebar, which no longer
        exists on apkmirror.com. The app page (``/apk/{pkg_name}/``) instead
        has several ``.listWidget`` sections built from the same ``.appRow``
        row markup (this app's own release history, "Popular in last 30
        days", "Latest Uploads", ...) -- only the "All versions" widget is
        this app's own releases, so it must be located by its heading text
        rather than matching ``.appRow`` page-wide.
        """
        url = self._get_versions_page_url(pkg_name)
        response = await self.get(url)
        tree = HTMLParser(response.text)
        releases: list[tuple[str, str]] = []
        all_versions_widget = None
        for widget in tree.css(".listWidget"):
            header = widget.css_first(".widgetHeader")
            if header and "all versions" in header.text(strip=True).lower():
                all_versions_widget = widget
                break
        if all_versions_widget is None:
            return releases
        for row in all_versions_widget.css(".appRow"):
            link = row.css_first("a.fontBlack")
            if link is None:
                continue
            href = link.attrs.get("href")
            if not href:
                continue
            releases.append((link.text(strip=True), f"{self.BASE_URL}{href}"))
        return releases

    async def get_versions(
        self,
        pkg_name: str,
        arch: ArchType = "universal",
        dpi: str = "nodpi",
        bundle_type: BundleType = "APK",
        exclude_alpha_beta: bool = True,
        match_any: bool = False,
    ) -> list[VersionInfo]:
        config = SearchConfig(
            apk_bundle=bundle_type,
            arch=arch,
            exclude_alpha_beta=exclude_alpha_beta,
            match_any=match_any,
        )
        releases = await self._list_release_pages(pkg_name)
        results: list[VersionInfo] = []
        for display_text, release_url in releases:
            version_match = re.search(r"\d+(?:\.\d+)+", display_text)
            if version_match is None:
                continue
            if exclude_alpha_beta and _is_prerelease(display_text, version_match):
                continue
            version = version_match.group()
            if match_any:
                # Caller only needs *a* version number to exist (e.g.
                # DownloadManager.resolve), not a specific installable
                # variant -- skip fetching every release page, which risks
                # a 429 from apkmirror.com for no benefit here.
                results.append(VersionInfo(version=version, url=release_url, arch=arch, dpi=dpi))
                continue
            try:
                release_html = await self.get(release_url, False)
            except RuntimeError:
                # A single throttled/removed release page shouldn't abort
                # enumerating the rest (e.g. a rate limit from fetching many
                # release pages back-to-back).
                continue
            download_url = self._search_variant(release_html.text, config)
            if download_url:
                results.append(
                    VersionInfo(
                        version=version,
                        url=download_url,
                        arch=arch,
                        dpi=dpi,
                    )
                )
        return results

    def _is_bundle(self, file_path: Path) -> bool:
        return is_apk_bundle(file_path)

    def _merge_splits(self, bundle_path: Path, output_path: Path) -> bool:
        return merge_apkm_splits(self.temp_dir, bundle_path, output_path)

    async def download(
        self,
        pkg_name: str,
        version: str | None,
        output_path: Path,
        arch: ArchType = "universal",
        dpi: str = "nodpi",
        bundle_type: BundleType = "APK",
        exclude_alpha_beta: bool = True,
    ) -> DownloadResult:
        config = SearchConfig(
            apk_bundle=bundle_type,
            arch=arch,
            exclude_alpha_beta=exclude_alpha_beta,
        )
        try:
            if version is None:
                versions = await self.get_versions(
                    pkg_name=pkg_name,
                    arch=arch,
                    dpi=dpi,
                    bundle_type=bundle_type,
                    exclude_alpha_beta=exclude_alpha_beta,
                )
                if not versions:
                    return DownloadResult(success=False, error="No versions found")
                version_info = versions[0]
                download_url = version_info.url
                version = version_info.version
                if download_url is None:
                    return DownloadResult(success=False, error="No download URL found")
            else:
                releases = await self._list_release_pages(pkg_name)
                download_url = None
                for display_text, release_url in releases:
                    version_match = re.search(r"\d+(?:\.\d+)+", display_text)
                    if version_match is None or version_match.group() != version:
                        continue
                    if exclude_alpha_beta and _is_prerelease(display_text, version_match):
                        continue
                    release_html = await self.get(release_url, False)
                    download_url = self._search_variant(release_html.text, config)
                    break
                if download_url is None:
                    return DownloadResult(
                        success=False,
                        error=f"Version {version} not found with specified criteria",
                    )

            final_download_url = await self._get_download_url(download_url)
            if final_download_url is None:
                return DownloadResult(success=False, error="Failed to get download URL")

            await self.save(final_download_url, output_path)

            if self._is_bundle(output_path):
                merged_path = output_path.with_suffix(".apk")
                await asyncio.to_thread(self._merge_splits, output_path, merged_path)
                output_path = merged_path

            return DownloadResult(success=True, file_path=output_path, version=version)

        except Exception as e:
            return DownloadResult(success=False, error=str(e))

    def close(self) -> None:
        super().close()
        if self._temp_dir is not None:
            shutil.rmtree(self._temp_dir, ignore_errors=True)
            self._temp_dir = None

    def __del__(self) -> None:
        self.close()
