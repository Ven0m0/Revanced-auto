"""Tests for scripts/builder/app_processor.py."""

# ruff: noqa: S101

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from scripts.builder.app_processor import AppProcessor, DownloadSource
from scripts.builder.config import AppConfig


class TestAppProcessor:
    @pytest.fixture
    def app_processor(self) -> AppProcessor:
        """Provide a mocked AppProcessor instance."""
        config_mock = MagicMock()
        java_runner_mock = MagicMock()
        return AppProcessor(config=config_mock, java_runner=java_runner_mock)

    @pytest.mark.parametrize(
        ("options", "expected_source"),
        [
            ({"apkmirror_dlurl": "https://apkmirror.com/some/path"}, DownloadSource.APKMIRROR),
            ({"uptodown_dlurl": "https://uptodown.com/some/path"}, DownloadSource.UPTODOWN),
            ({"apkpure_dlurl": "https://apkpure.com/some/path"}, DownloadSource.APKPURE),
            ({"archive_dlurl": "https://archive.org/some/path"}, DownloadSource.ARCHIVE),
            ({"aptoide_dlurl": "https://aptoide.com/some/path"}, DownloadSource.APTOIDE),
            ({"apkmonk_dlurl": "https://apkmonk.com/some/path"}, DownloadSource.APKMonk),
            ({}, DownloadSource.APKMIRROR),
            ({"other_dlurl": "https://example.com/"}, DownloadSource.APKMIRROR),
        ],
    )
    def test_determine_download_source(
        self,
        app_processor: AppProcessor,
        options: dict[str, str],
        expected_source: DownloadSource,
    ) -> None:
        """Test download source resolution based on app configuration."""
        app_config = AppConfig(name="TestApp", options=options)

        # We need to call the private method for this specific test
        # pylint: disable=protected-access
        source = app_processor._determine_download_source(app_config)

        assert source == expected_source
