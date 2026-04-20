"""APKMirror scraper module for APK version retrieval and downloads."""

from __future__ import annotations

import asyncio
import re
import subprocess
from dataclasses import dataclass
from enum import Enum
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


class ApkBundle(Enum):
    """APK bundle type."""

    APK = "APK"
    BUNDLE = "BUNDLE"


@dataclass(frozen=True, slots=True)
class SearchConfig:
    """Configuration for APKMirror search.

    Attributes:
        apk_bundle: Bundle type (APK or BUNDLE).
        dpi: Screen DPI (e.g., nodpi).
        arch: Target architecture.
        exclude_alpha_beta: Exclude alpha/beta versions.

    """

    apk_bundle: BundleType
    dpi: str
    arch: ArchType
    exclude_alpha_beta: bool = True


@dataclass(frozen=True, slots=True)
class RowData:
    """Structured data extracted from a table row.

    Attributes:
        version: APK version string.
        size: File size string.
        bundle: Bundle type.
        arch: Architecture string.
        android_ver: Minimum Android version.
        dpi: Screen DPI.

    """

    version: str
    size: str
    bundle: str
    arch: str
    android_ver: str
    dpi: str


_MIN_ROW_FIELDS: int = 6


def get_target_archs(arch: ArchType) -> list[str]:
    """Get list of compatible architectures based on requested arch.

    Args:
        arch: Requested architecture string.

    Returns:
        Ordered list of acceptable architectures including fallbacks.

    """
    base_archs: list[str] = ["universal", "noarch", "arm64-v8a + armeabi-v7a"]

    match arch:
        case "all":
            return base_archs
        case _:
            return [arch, *base_archs]


def _row_text_nodes(row: HTMLParser) -> list[str]:
    """Extract ordered text nodes from a table row.

    Args:
        row: selectolax Node for the table row.

    Returns:
        List of stripped, non-empty text strings in document order.

    """
    texts: list[str] = []
    for node in row.css("*"):
        t = node.text(deep=False)
        if t and (s := t.strip()):
            texts.append(s)
    return texts


def _parse_row_data(text_nodes: list[str]) -> RowData | None:
    """Parse row text nodes into structured RowData.

    Args:
        text_nodes: List of text strings from the row.

    Returns:
        RowData if enough fields are present, None otherwise.

    """
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
    """Check if a row matches the search configuration.

    Args:
        row_data: Structured row data.
        config: Search configuration.
        target_archs: List of acceptable architectures.

    Returns:
        True if the row matches all criteria.

    """
    return row_data.bundle == config.apk_bundle and row_data.dpi == config.dpi and row_data.arch in target_archs


def _extract_download_url(row: HTMLParser) -> str | None:
    """Extract the download URL from a matching row.

    Args:
        row: The matching table row node.

    Returns:
        The full download URL if found, None otherwise.

    """
    link = row.css_first("div > a")
    if link is None:
        return None

    href = link.attrs.get("href")
    if not href:
        return None

    return f"https://www.apkmirror.com{href}"


def _parse_rows(tree: HTMLParser) -> list[HTMLParser]:
    """Parse all table rows from the HTML tree.

    Args:
        tree: Parsed HTML tree.

    Returns:
        List of row nodes matching the expected structure.

    """
    return tree.css("div.table-row.headerFont")


class APKMirror(ScraperBase):
    """APKMirror scraper for APK version retrieval and downloads.

    Supports APK and BUNDLE types with architecture and DPI filtering.
    Excludes alpha/beta versions by default.

    Attributes:
        source: The download source identifier.

    """

    BASE_URL = "https://www.apkmirror.com"
    APK_ARCH_PATH = BASE_URL + "/apk"

    def __init__(self) -> None:
        super().__init__(DownloadSource.APKMIRROR)
        self._temp_dir: Path | None = None

    @property
    def temp_dir(self) -> Path:
        """Get or create temporary directory for downloads."""
        if self._temp_dir is None:
            import tempfile

            self._temp_dir = Path(tempfile.mkdtemp(prefix="apkmirror_"))
        return self._temp_dir

    def get_package_name(self, url: str) -> str | None:
        """Extract package name from APKMirror URL.

        Args:
            url: APKMirror URL in format https://www.apkmirror.com/apk/{org}/{name}/

        Returns:
            Package name if found, None otherwise.

        """
        pattern = r"apkmirror\.com/apk/([^/]+)/([^/]+)/?"
        match = re.search(pattern, url)
        if match:
            return match.group(2)
        return None

    def _get_versions_page_url(self, pkg_name: str) -> str:
        """Get the APKMirror versions page URL for a package.

        Args:
            pkg_name: Package name (app identifier).

        Returns:
            Full URL to the versions page.

        """
        return f"{self.APK_ARCH_PATH}/{pkg_name}/"

    def _search_variant(
        self,
        html_content: str,
        config: SearchConfig,
    ) -> str | None:
        """Search for matching APK variant in HTML content.

        Args:
            html_content: HTML string from APKMirror release page.
            config: Search configuration.

        Returns:
            Download URL if found, None otherwise.

        """
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
        """Find the actual download link from variant page.

        Args:
            variant_page_html: HTML content from variant page.

        Returns:
            Direct download URL if found, None otherwise.

        """
        tree = HTMLParser(variant_page_html)
        download_btn = tree.css_first("a.btn-flat.download-btn")
        if download_btn is None:
            return None

        href = download_btn.attrs.get("href")
        if not href:
            return None

        return f"{self.BASE_URL}{href}"

    def _get_download_url(self, variant_url: str) -> str | None:
        """Get the actual file download URL from variant page.

        Args:
            variant_url: URL of the APK variant page.

        Returns:
            Direct download URL if found, None otherwise.

        """
        response = self.get(variant_url)
        return self._find_download_link(response.text)

    async def get_versions(
        self,
        pkg_name: str,
        arch: ArchType = "universal",
        dpi: str = "nodpi",
        bundle_type: BundleType = "APK",
        exclude_alpha_beta: bool = True,
    ) -> list[VersionInfo]:
        """Get available versions from APKMirror.

        Args:
            pkg_name: Package name (app identifier).
            arch: Target architecture (default: universal).
            dpi: Screen DPI filter (default: nodpi).
            bundle_type: Bundle type - APK or BUNDLE (default: APK).
            exclude_alpha_beta: Exclude alpha/beta versions (default: True).

        Returns:
            List of VersionInfo objects with version and URL.

        """
        config = SearchConfig(
            apk_bundle=bundle_type,
            dpi=dpi,
            arch=arch,
            exclude_alpha_beta=exclude_alpha_beta,
        )

        versions_url = self._get_versions_page_url(pkg_name)
        response = await asyncio.get_event_loop().run_in_executor(None, self.get, versions_url)

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

            variant_html = await asyncio.get_event_loop().run_in_executor(None, self.get, variant_url, False)

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
        """Check if a file is a bundle (XAPK/APKM).

        Args:
            file_path: Path to the file.

        Returns:
            True if file has bundle extension.

        """
        return file_path.suffix.lower() in (".apkm", ".xapk")

    def _merge_splits(self, bundle_path: Path, output_path: Path) -> bool:
        """Merge split APKs using APKEditor.

        Args:
            bundle_path: Path to the bundle file.
            output_path: Path for the merged output.

        Returns:
            True if merge succeeded, False otherwise.

        """
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
            result = subprocess.run(
                [
                    "java",
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
        subprocess.run(
            ["zip", "-0rq", str(zip_path), "."],
            cwd=extract_dir,
            check=True,
        )

        import shutil

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
        """Download a specific version from APKMirror.

        Args:
            pkg_name: Package name (app identifier).
            version: Version to download (None for latest).
            output_path: Path to save the downloaded file.
            arch: Target architecture (default: universal).
            dpi: Screen DPI filter (default: nodpi).
            bundle_type: Bundle type - APK or BUNDLE (default: APK).
            exclude_alpha_beta: Exclude alpha/beta versions (default: True).

        Returns:
            DownloadResult with success status, file path, and version.

        """
        config = SearchConfig(
            apk_bundle=bundle_type,
            dpi=dpi,
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
                    return DownloadResult(
                        success=False,
                        error="No versions found",
                    )
                version_info = versions[0]
                download_url = version_info.url
                version = version_info.version
            else:
                versions_url = self._get_versions_page_url(pkg_name)
                response = await asyncio.get_event_loop().run_in_executor(None, self.get, versions_url)

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

                    variant_html = await asyncio.get_event_loop().run_in_executor(None, self.get, variant_url, False)

                    download_url = self._search_variant(variant_html.text, config)
                    break

                if download_url is None:
                    return DownloadResult(
                        success=False,
                        error=f"Version {version} not found with specified criteria",
                    )

            final_download_url = await asyncio.get_event_loop().run_in_executor(
                None, self._get_download_url, download_url
            )
            if final_download_url is None:
                return DownloadResult(
                    success=False,
                    error="Failed to get download URL",
                )

            await asyncio.get_event_loop().run_in_executor(None, self._download_file, final_download_url, output_path)

            if self._is_bundle(output_path):
                merged_path = output_path.with_suffix(".apk")
                await asyncio.get_event_loop().run_in_executor(None, self._merge_splits, output_path, merged_path)
                output_path = merged_path

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

    def _download_file(self, url: str, output_path: Path) -> None:
        """Download a file from URL to output path.

        Args:
            url: Download URL.
            output_path: Path to save the file.

        """
        response = self.get(url, use_cache=False)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(response.content)

    def close(self) -> None:
        """Close the scraper and clean up resources."""
        super().close()
        if self._temp_dir is not None:
            import shutil

            shutil.rmtree(self._temp_dir, ignore_errors=True)
            self._temp_dir = None

    def __del__(self) -> None:
        """Destructor to ensure cleanup."""
        self.close()
