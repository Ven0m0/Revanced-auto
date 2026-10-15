"""Tests for scripts/scrapers/base.py's shared retry/rate-limit logic."""

# ruff: noqa: S101

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from scripts.scrapers.base import DownloadSource, ScraperBase


def _make_response(status_code: int, headers: dict[str, str] | None = None) -> MagicMock:
    response = MagicMock()
    response.status_code = status_code
    response.headers = headers or {}
    response.raise_for_status = MagicMock()
    return response


@pytest.mark.asyncio
async def test_retries_after_429_then_succeeds() -> None:
    scraper = ScraperBase(DownloadSource.APKMIRROR)
    rate_limited = _make_response(429)
    ok = _make_response(200)
    mock_session = MagicMock()
    mock_session.request = AsyncMock(side_effect=[rate_limited, ok])

    with (
        patch.object(ScraperBase, "session", new_callable=lambda: property(lambda _self: mock_session)),
        patch("scripts.scrapers.base.asyncio.sleep", new=AsyncMock()) as mock_sleep,
    ):
        result = await scraper._request_with_retry("https://example.com")

    assert result is ok
    assert mock_session.request.call_count == 2
    mock_sleep.assert_awaited()


@pytest.mark.asyncio
async def test_429_honors_retry_after_header() -> None:
    scraper = ScraperBase(DownloadSource.APKMIRROR)
    rate_limited = _make_response(429, headers={"retry-after": "7"})
    ok = _make_response(200)
    mock_session = MagicMock()
    mock_session.request = AsyncMock(side_effect=[rate_limited, ok])

    with (
        patch.object(ScraperBase, "session", new_callable=lambda: property(lambda _self: mock_session)),
        patch("scripts.scrapers.base.asyncio.sleep", new=AsyncMock()) as mock_sleep,
    ):
        await scraper._request_with_retry("https://example.com")

    mock_sleep.assert_any_await(7.0)


@pytest.mark.asyncio
async def test_429_without_retry_after_uses_escalating_delay() -> None:
    scraper = ScraperBase(DownloadSource.APKMIRROR)
    rate_limited = _make_response(429)
    ok = _make_response(200)
    mock_session = MagicMock()
    mock_session.request = AsyncMock(side_effect=[rate_limited, ok])

    with (
        patch.object(ScraperBase, "session", new_callable=lambda: property(lambda _self: mock_session)),
        patch("scripts.scrapers.base.asyncio.sleep", new=AsyncMock()) as mock_sleep,
    ):
        await scraper._request_with_retry("https://example.com")

    waited = mock_sleep.await_args_list[0].args[0]
    assert waited >= scraper.RATE_LIMIT_DELAY
