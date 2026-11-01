"""Tests for the Cloudflare-challenge browser launcher."""

# ruff: noqa: S101

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from scripts.scrapers.browser import ChallengeBrowser


def _fake_nodriver() -> MagicMock:
    nodriver = MagicMock()
    nodriver.Config.return_value = MagicMock(browser_executable_path="chrome", return_value=["--x"])
    nodriver.util.free_port.return_value = 9222
    return nodriver


def _fake_process(returncode: int | None) -> MagicMock:
    process = MagicMock(returncode=returncode)
    process.wait = AsyncMock()
    return process


@pytest.mark.asyncio
async def test_launch_reports_chrome_crash() -> None:
    with (
        patch.dict("sys.modules", {"nodriver": _fake_nodriver()}),
        patch("asyncio.create_subprocess_exec", new=AsyncMock(return_value=_fake_process(1))),
        pytest.raises(RuntimeError, match="exited with code 1"),
    ):
        await ChallengeBrowser()._launch()


@pytest.mark.asyncio
async def test_launch_kills_chrome_when_port_never_opens() -> None:
    process = _fake_process(None)
    with (
        patch.dict("sys.modules", {"nodriver": _fake_nodriver()}),
        patch("asyncio.create_subprocess_exec", new=AsyncMock(return_value=process)),
        patch("asyncio.open_connection", new=AsyncMock(side_effect=OSError)),
        patch("asyncio.sleep", new=AsyncMock()),
        patch("scripts.scrapers.browser._LAUNCH_TIMEOUT_S", 2),
        pytest.raises(RuntimeError, match="did not open its debug port"),
    ):
        await ChallengeBrowser()._launch()
    process.kill.assert_called_once()


@pytest.mark.asyncio
async def test_open_reloads_a_stuck_challenge() -> None:
    tab = MagicMock(sleep=AsyncMock())
    tab.reload = AsyncMock(side_effect=lambda: setattr(tab, "title", "Discord - APKMirror"))
    tab.title = "Just a moment..."
    tab.evaluate = AsyncMock(side_effect=lambda _js: tab.title)
    browser = ChallengeBrowser()
    browser._browser = MagicMock(get=AsyncMock(return_value=tab))
    with patch("scripts.scrapers.browser._CHALLENGE_RELOAD_S", 3):
        assert await browser._open("https://example.com") is tab
    tab.reload.assert_awaited_once()
