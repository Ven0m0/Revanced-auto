"""ArchiveScraper download matching."""

# ruff: noqa: S101

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, patch

from scripts.scrapers.archive import ArchiveScraper
from scripts.scrapers.base import VersionInfo

if TYPE_CHECKING:
    from pathlib import Path

_URL = "https://archive.org/download/jhc-apks/apks/com.example/com.example-21.20.405-all.apk"


def _download(tmp_path: Path, version: str) -> bool:
    scraper = ArchiveScraper()
    listing = [VersionInfo(version="21.20.405", url=_URL, arch="all")]
    with (
        patch.object(scraper, "get_versions", AsyncMock(return_value=listing)),
        patch.object(scraper, "save", AsyncMock()),
    ):
        result = asyncio.run(scraper.download("com.example", version, tmp_path / "a.apk", arch="arm64-v8a"))
    return result.success


def test_universal_build_satisfies_requested_arch(tmp_path: Path) -> None:
    assert _download(tmp_path, "21.20.405")


def test_version_mismatch_still_fails(tmp_path: Path) -> None:
    assert not _download(tmp_path, "21.20.406")
