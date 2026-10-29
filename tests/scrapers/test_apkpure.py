"""Tests for the APKPure scraper."""

# ruff: noqa: S101

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from scripts.scrapers.apkpure import APKPureScraper
from scripts.scrapers.base import ChallengeError

_CURRENT_PAGE = """
<div class="ver-top-down" data-dt-version="47.6.2"></div>
<ul class="version-list">
  <li class="version dt-version-item" data-dt-version="47.6.2"></li>
  <li class="version dt-version-item" data-dt-version="44.9.2"></li>
  <li class="version dt-version-item" data-dt-version="47.6.2"></li>
</ul>
"""
_LEGACY_PAGE = '<div class="ver-item"><a href="/x"><span class="ver-item-n">1.2.3</span></a></div>'
_URL = "https://apkpure.net/tiktok/com.zhiliaoapp.musically/versions"


def test_parse_versions_page_reads_the_current_list_without_repeats() -> None:
    versions = APKPureScraper()._parse_versions_page(_CURRENT_PAGE)

    assert [v.version for v in versions] == ["47.6.2", "44.9.2"]


def test_parse_versions_page_still_reads_the_legacy_list() -> None:
    assert [v.version for v in APKPureScraper()._parse_versions_page(_LEGACY_PAGE)] == ["1.2.3"]


class _FakeBrowser:
    instances: list[_FakeBrowser] = []  # noqa: RUF012

    def __init__(self) -> None:
        self.fetch_html = AsyncMock(return_value=_CURRENT_PAGE)
        self.aclose = AsyncMock()
        _FakeBrowser.instances.append(self)


@pytest.mark.asyncio
async def test_get_versions_uses_the_browser_when_http_is_challenged_and_closes_it() -> None:
    _FakeBrowser.instances.clear()

    with (
        patch.object(APKPureScraper, "get", new=AsyncMock(side_effect=ChallengeError("challenge"))),
        patch("scripts.scrapers.apkpure.ChallengeBrowser", _FakeBrowser),
    ):
        versions = await APKPureScraper().get_versions("tiktok/com.zhiliaoapp.musically")

    assert [v.version for v in versions] == ["47.6.2", "44.9.2"]
    _FakeBrowser.instances[0].fetch_html.assert_awaited_once_with(_URL)
    _FakeBrowser.instances[0].aclose.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_versions_retries_in_the_browser_when_http_returns_a_challenge_stub() -> None:
    _FakeBrowser.instances.clear()

    with (
        patch.object(APKPureScraper, "get", new=AsyncMock(return_value=SimpleNamespace(text="<html></html>"))),
        patch("scripts.scrapers.apkpure.ChallengeBrowser", _FakeBrowser),
    ):
        versions = await APKPureScraper().get_versions("tiktok/com.zhiliaoapp.musically")

    assert [v.version for v in versions] == ["47.6.2", "44.9.2"]
    assert len(_FakeBrowser.instances) == 1


@pytest.mark.asyncio
async def test_get_versions_never_starts_a_browser_when_http_works() -> None:
    _FakeBrowser.instances.clear()

    with (
        patch.object(APKPureScraper, "get", new=AsyncMock(return_value=SimpleNamespace(text=_CURRENT_PAGE))),
        patch("scripts.scrapers.apkpure.ChallengeBrowser", _FakeBrowser),
    ):
        versions = await APKPureScraper().get_versions("tiktok/com.zhiliaoapp.musically")

    assert len(versions) == 2
    assert _FakeBrowser.instances == []
