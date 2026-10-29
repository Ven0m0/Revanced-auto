"""Tests for the Uptodown scraper."""

# ruff: noqa: S101

from __future__ import annotations

import json
from types import SimpleNamespace
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, patch

import pytest

from scripts.scrapers.uptodown import UptodownScraper

if TYPE_CHECKING:
    from pathlib import Path

_BASE = "https://tiktok.en.uptodown.com/android"
_VERSIONS_PAGE = '<h1 id="detail-app-name" data-code="150731"></h1>'


def _row(version: str, version_id: int) -> dict[str, object]:
    return {
        "version": version,
        "kindFile": "apk",
        "versionURL": {"url": _BASE, "extraURL": "download", "versionID": version_id},
    }


def _fake_get(pages: dict[str, str]) -> AsyncMock:
    async def get(url: str, use_cache: bool = True) -> SimpleNamespace:  # noqa: ARG001, FBT001, FBT002
        if url not in pages:
            msg = f"HTTP 404 for {url}"
            raise RuntimeError(msg)
        return SimpleNamespace(text=pages[url])

    return AsyncMock(side_effect=get)


def _pages(*json_pages: list[dict[str, object]]) -> dict[str, str]:
    pages = {f"{_BASE}/versions": _VERSIONS_PAGE}
    for number, rows in enumerate(json_pages, start=1):
        pages[f"{_BASE}/apps/150731/versions/{number}"] = json.dumps({"success": 1, "data": rows})
    return pages


@pytest.mark.asyncio
async def test_get_versions_reads_the_json_pages_until_one_is_empty() -> None:
    pages = _pages([_row("47.4.3", 3), _row("47.4.2", 2)], [_row("47.4.1", 1)], [])

    with patch.object(UptodownScraper, "get", new=_fake_get(pages)):
        versions = await UptodownScraper().get_versions("tiktok")

    assert [v.version for v in versions] == ["47.4.3", "47.4.2", "47.4.1"]
    assert versions[0].url == f"{_BASE}/download/3"


@pytest.mark.asyncio
async def test_get_versions_drops_repeated_versions() -> None:
    pages = _pages([_row("1.0", 1)], [_row("1.0", 2)], [])

    with patch.object(UptodownScraper, "get", new=_fake_get(pages)):
        versions = await UptodownScraper().get_versions("tiktok")

    assert [v.version for v in versions] == ["1.0"]


@pytest.mark.asyncio
async def test_get_versions_is_empty_without_the_app_code() -> None:
    with patch.object(UptodownScraper, "get", new=_fake_get({f"{_BASE}/versions": "<html></html>"})):
        assert await UptodownScraper().get_versions("tiktok") == []


class _FakeBrowser:
    instances: list[_FakeBrowser] = []  # noqa: RUF012

    def __init__(self) -> None:
        self.capture_download_url = AsyncMock(return_value="https://dw.uptodown.com/dwn/token/")
        self.aclose = AsyncMock()
        _FakeBrowser.instances.append(self)


@pytest.mark.asyncio
async def test_download_captures_the_signed_url_in_a_browser_then_saves_it(tmp_path: Path) -> None:
    _FakeBrowser.instances.clear()
    save = AsyncMock()

    with (
        patch.object(UptodownScraper, "get", new=_fake_get(_pages([_row("47.4.3", 3)], []))),
        patch.object(UptodownScraper, "save", new=save),
        patch("scripts.scrapers.uptodown.ChallengeBrowser", _FakeBrowser),
    ):
        result = await UptodownScraper().download("tiktok", "47.4.3", tmp_path / "app.apk")

    assert result.success
    assert result.version == "47.4.3"
    _FakeBrowser.instances[0].capture_download_url.assert_awaited_once_with(
        f"{_BASE}/download/3", "#detail-download-button"
    )
    save.assert_awaited_once_with("https://dw.uptodown.com/dwn/token/", tmp_path / "app.apk")
    _FakeBrowser.instances[0].aclose.assert_awaited_once()


@pytest.mark.asyncio
async def test_download_reports_a_browser_failure_and_still_closes_it(tmp_path: Path) -> None:
    _FakeBrowser.instances.clear()

    class _Failing(_FakeBrowser):
        def __init__(self) -> None:
            super().__init__()
            self.capture_download_url = AsyncMock(side_effect=RuntimeError("no token"))

    with (
        patch.object(UptodownScraper, "get", new=_fake_get(_pages([_row("47.4.3", 3)], []))),
        patch("scripts.scrapers.uptodown.ChallengeBrowser", _Failing),
    ):
        result = await UptodownScraper().download("tiktok", "47.4.3", tmp_path / "app.apk")

    assert not result.success
    assert result.error == "no token"
    _FakeBrowser.instances[0].aclose.assert_awaited_once()


@pytest.mark.asyncio
async def test_download_of_an_unlisted_version_fails_without_a_browser(tmp_path: Path) -> None:
    _FakeBrowser.instances.clear()

    with (
        patch.object(UptodownScraper, "get", new=_fake_get(_pages([_row("47.4.3", 3)], []))),
        patch("scripts.scrapers.uptodown.ChallengeBrowser", _FakeBrowser),
    ):
        result = await UptodownScraper().download("tiktok", "1.0.0", tmp_path / "app.apk")

    assert not result.success
    assert "not found" in (result.error or "")
    assert _FakeBrowser.instances == []
