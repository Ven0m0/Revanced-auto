"""Tests for DownloadManager.resolve version matching against patch-compatible lists."""

# ruff: noqa: S101

from __future__ import annotations

from typing import TYPE_CHECKING

from scripts.scrapers.base import DownloadResult, DownloadSource, ScraperBase, VersionInfo
from scripts.scrapers.download_manager import DownloadManager

if TYPE_CHECKING:
    from pathlib import Path


class _VersionsScraper(ScraperBase):
    def __init__(self, source: DownloadSource, versions: list[str]) -> None:
        super().__init__(source)
        self.versions = versions

    async def get_versions(self, pkg_name: str, **kwargs: object) -> list[VersionInfo]:
        del pkg_name, kwargs
        return [VersionInfo(version=v) for v in self.versions]

    async def download(self, pkg_name: str, version: str | None, output_path: Path, **kwargs: object) -> DownloadResult:
        raise NotImplementedError


def _resolve(store_versions: list[str], compatible: list[str]) -> tuple[str, str]:
    manager = DownloadManager()
    manager._scrapers[DownloadSource.GITHUB] = _VersionsScraper(DownloadSource.GITHUB, store_versions)
    return manager.resolve("owner/repo", DownloadSource.GITHUB, compatible=compatible)


def test_store_v_prefix_matches_bare_compatible_and_keeps_source_string() -> None:
    assert _resolve(["v1.2.3", "v1.3.0"], ["1.2.3"]) == ("v1.2.3", "v1.2.3")


def test_compatible_v_prefix_matches_bare_store_version() -> None:
    assert _resolve(["1.2.3", "1.3.0"], ["v1.2.3"]) == ("1.2.3", "1.2.3")
