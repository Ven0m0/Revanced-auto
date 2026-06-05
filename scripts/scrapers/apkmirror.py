"""APKMirror scraper module for APK version retrieval and downloads."""

from __future__ import annotations

import asyncio
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from selectolax.parser import HTMLParser

from scripts.scrapers.base import (
    DownloadResult,
    DownloadSource,
    ScraperBase,
    VersionInfo,
)

type ArchType = Literal["universal", "noarch", "arm64-v8a", "armeabi-v7a", "arm64-v8a + armeabi-v7a"]
type BundleType = Literal["APK", "BUNDLE"]


@dataclass(frozen=True, slots=True)
class SearchConfig:
    apk_bundle: BundleType
    dpi: str
    arch: ArchType
    exclude_alpha_beta: bool = True


@dataclass(frozen=True, slots=True)
class RowData:
    version: str
    size: str
    bundle: str
    arch: str
    android_ver: str
    dpi: str


_MIN_ROW_FIELDS: int = 6


def get_target_archs(arch: ArchType) -> list[str]:
    base_archs: list[str] = ["universal", "noarch", "arm64-v8a + armeabi-v7a"]
    match arch:
        case "all":
            return base_archs
        case _:
            return [arch, *base_archs]


def _row_text_nodes(row: HTMLParser) -> list[str]:
    texts: list[str] = []
    for node in row.css("*"):
        t = node.text(deep=False)
        if t and (s := t.strip()):
            texts.append(s)
    return texts


def _parse_row_data(text_nodes: list[str]) -> RowData | None:
    if len(text_nodes) < _MIN_ROW_FIELDS:
        return None
    return RowData(
        version=text_nodes[0],
        size=text_nodes[1],
        bundle=text_nodes[2],
        arch=text_nodes[3],
        android_ver=text_nodes[4],
        dpi=text_nodes[5],
    )


def _row_matches(row_data: RowData, config: SearchConfig, target_archs: list[str]) -> bool:
    return row_data.bundle == config.apk_bundle and row_data.dpi == config.dpi and row_data.arch in target_archs


def _extract_download_url(row: HTMLParser) -> str | None:
    link = row.css_first("div > a")
    if link is None:
        return None
    href = link.attrs.get("href")
    if not href:
        return None
    return f"https://www.apkmirror.com{href}"


def _parse_rows(tree: HTMLParser) -> list[HTMLParser]:
    return tree.css("div.table-row.headerFont")


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

    def get_package_name(self, url: str) -> str | None:
        pattern = r"apkmirror\.com/apk/([^/]+)/([^/]+)/?"
        match = re.search(pattern, url)
        if match:
            return match.group(2)
        return None

    def _get_versions_page_url(self, pkg_name: str) -> str:
        return f"{self.APK_ARCH_PATH}/{pkg_name}/"

    def _search_variant(self, html_content: str, config: SearchConfig) -> str | None:
        tree = HTMLParser(html_content)
        rows = _parse_rows(tree)
        if not rows:
            return None
        target_archs = get_target_archs(config.arch)
        for row in rows:
            text_nodes = _row_text_nodes(row)
            row_data = _parse_row_data(text_nodes)
            if row_data is None:
                continue
            if config.exclude_alpha_beta and (
                "alpha" in row_data.version.lower() or "beta" in row_data.version.lower()
            ):
                continue
            if not _row_matches(row_data, config, target_archs):
                continue
            url = _extract_download_url(row)
            if url:
                return url
        return None

    def _find_download_link(self, variant_page_html: str) -> str | None:
        tree = HTMLParser(variant_page_html)
        download_btn = tree.css_first("a.btn-flat.download-btn")
        if download_btn is None:
            return None
        href = download_btn.attrs.get("href")
        if not href:
            return None
        return f"{self.BASE_URL}{href}"

    async def _get_download_url(self, variant_url: str) -> str | None:
        response = await self.get(variant_url)
        return self._find_download_link(response.text)

    async def get_versions(
        self,
        pkg_name: str,
        arch: ArchType = "universal",
        dpi: str = "nodpi",
        bundle_type: BundleType = "APK",
        exclude_alpha_beta: bool = True,
    ) -> list[VersionInfo]:
        config = SearchConfig(
            apk_bundle=bundle_type,
            dpi=dpi,
            arch=arch,
            exclude_alpha_beta=exclude_alpha_beta,
        )
        versions_url = self._get_versions_page_url(pkg_name)
        response = await self.get(versions_url)
        tree = HTMLParser(response.text)
        version_links = tree.css("div.version-fed-list > div")
        results: list[VersionInfo] = []
        for link_container in version_links:
            link = link_container.css_first("a")
            if link is None:
                continue
            href = link.attrs.get("href")
            if not href:
                continue
            version_text = link.css_first("span")
            version = version_text.text() if version_text else ""
            if exclude_alpha_beta and ("alpha" in version.lower() or "beta" in version.lower()):
                continue
            variant_url = f"{self.BASE_URL}{href}"
            variant_html = await self.get(variant_url, False)
            download_url = self._search_variant(variant_html.text, config)
            if download_url:
                results.append(
                    VersionInfo(
                        version=version.strip(),
                        url=download_url,
                        arch=arch,
                        dpi=dpi,
                    )
                )
        return results

    def _is_bundle(self, file_path: Path) -> bool:
        return file_path.suffix.lower() in (".apkm", ".xapk")

    def _merge_splits(self, bundle_path: Path, output_path: Path) -> bool:
        from scripts.utils.network import gh_dl

        apkeditor_jar = self.temp_dir / "apkeditor.jar"
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
                    "java", "-jar", str(apkeditor_jar), "merge",
                    "-i", str(bundle_path), "-o", f"{bundle_path}.mzip",
                    "-clean-meta", "-f",
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
            dpi=dpi,
            arch=arch,
            exclude_alpha_beta=exclude_alpha_beta,
        )
        try:
            if version is None:
                versions = await self.get_versions(
                    pkg_name=pkg_name, arch=arch, dpi=dpi,
                    bundle_type=bundle_type, exclude_alpha_beta=exclude_alpha_beta,
                )
                if not versions:
                    return DownloadResult(success=False, error="No versions found")
                version_info = versions[0]
                download_url = version_info.url
                version = version_info.version
            else:
                versions_url = self._get_versions_page_url(pkg_name)
                response = await self.get(versions_url)
                tree = HTMLParser(response.text)
                version_links = tree.css("div.version-fed-list > div")
                download_url = None
                for link_container in version_links:
                    link = link_container.css_first("a")
                    if link is None:
                        continue
                    href = link.attrs.get("href")
                    if not href:
                        continue
                    version_text = link.css_first("span")
                    version_str = version_text.text() if version_text else ""
                    if version_str.strip() != version:
                        continue
                    if exclude_alpha_beta and ("alpha" in version_str.lower() or "beta" in version_str.lower()):
                        continue
                    variant_url = f"{self.BASE_URL}{href}"
                    variant_html = await self.get(variant_url, False)
                    download_url = self._search_variant(variant_html.text, config)
                    break
                if download_url is None:
                    return DownloadResult(
                        success=False,
                        error=f"Version {version} not found with specified criteria",
                    )

            final_download_url = await self._get_download_url(download_url)
            if final_download_url is None:
                return DownloadResult(success=False, error="Failed to get download URL")

            await self._download_file(final_download_url, output_path)

            if self._is_bundle(output_path):
                merged_path = output_path.with_suffix(".apk")
                await asyncio.to_thread(self._merge_splits, output_path, merged_path)
                output_path = merged_path

            return DownloadResult(success=True, file_path=output_path, version=version)

        except Exception as e:
            return DownloadResult(success=False, error=str(e))

    async def _download_file(self, url: str, output_path: Path) -> None:
        response = await self.get(url, use_cache=False)
        await asyncio.to_thread(output_path.parent.mkdir, parents=True, exist_ok=True)
        await asyncio.to_thread(output_path.write_bytes, response.content)

    def close(self) -> None:
        super().close()
        if self._temp_dir is not None:
            shutil.rmtree(self._temp_dir, ignore_errors=True)
            self._temp_dir = None

    def __del__(self) -> None:
        self.close()
