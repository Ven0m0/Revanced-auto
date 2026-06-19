"""Tests for scripts/builder/app_processor.py."""

# ruff: noqa: S101

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from scripts.builder.app_processor import (
    AppProcessor,
    Architecture,
    DownloadSource,
    _cli_artifact_name,
    _patches_artifact_name,
)
from scripts.builder.config import AppConfig


class TestAppProcessorArchitecture:
    """Tests for AppProcessor._parse_architecture."""

    @pytest.fixture
    def processor(self) -> AppProcessor:
        """Provide a mocked AppProcessor instance."""
        config_mock = MagicMock()
        java_runner_mock = MagicMock()
        return AppProcessor(config=config_mock, java_runner=java_runner_mock)

    def test_parse_architecture_default(self, processor: AppProcessor) -> None:
        """Test default architecture (no arch specified)."""
        config = AppConfig(name="TestApp", options={})
        assert processor._parse_architecture(config) == Architecture.ALL

    @pytest.mark.parametrize(
        ("arch_str", "expected_arch"),
        [
            ("arm64-v8a", Architecture.ARM64_V8A),
            ("arm-v7a", Architecture.ARM_V7A),
            ("both", Architecture.BOTH),
            ("all", Architecture.ALL),
        ],
    )
    def test_parse_architecture_valid(
        self,
        processor: AppProcessor,
        arch_str: str,
        expected_arch: Architecture,
    ) -> None:
        """Test valid architecture strings."""
        config = AppConfig(name="TestApp", options={"arch": arch_str})
        assert processor._parse_architecture(config) == expected_arch

    def test_parse_architecture_invalid(self, processor: AppProcessor) -> None:
        """Test invalid architecture raises ValueError."""
        config = AppConfig(name="TestApp", options={"arch": "invalid-arch"})
        with pytest.raises(ValueError, match="Invalid architecture: invalid-arch"):
            processor._parse_architecture(config)


class TestAppProcessorDownloadSource:
    """Tests for AppProcessor._determine_download_source."""

    @pytest.fixture
    def processor(self) -> AppProcessor:
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
        processor: AppProcessor,
        options: dict[str, str],
        expected_source: DownloadSource,
    ) -> None:
        """Test download source resolution based on app configuration."""
        app_config = AppConfig(name="TestApp", options=options)
        source = processor._determine_download_source(app_config)
        assert source == expected_source


class TestArtifactNameDerivation:
    """Tests for CLI / patches artifact name derivation from repo slugs.

    These guard the regression where the hardcoded ``revanced-cli-`` and
    ``revanced-patches-`` URLs broke downloads for Morphe, Piko, and other
    non-ReVanced sources.
    """

    @pytest.mark.parametrize(
        ("repo", "expected"),
        [
            ("MorpheApp/morphe-cli", "morphe-cli"),
            ("ReVanced/revanced-cli", "revanced-cli"),
            ("inotia00/revanced-cli", "revanced-cli"),
            ("j-hc/revanced-cli", "revanced-cli"),
            ("jkennethcarino/adobo", "adobo"),
        ],
    )
    def test_cli_artifact_name(self, repo: str, expected: str) -> None:
        assert _cli_artifact_name(repo) == expected

    @pytest.mark.parametrize(
        ("repo", "expected"),
        [
            ("MorpheApp/morphe-patches", "morphe-patches"),
            ("ReVanced/revanced-patches", "revanced-patches"),
            ("anddea/revanced-patches", "revanced-patches"),
            ("crimera/piko", "piko"),
            ("wchill/patcheddit", "patcheddit"),
            ("jkennethcarino/adobo", "adobo"),
        ],
    )
    def test_patches_artifact_name(self, repo: str, expected: str) -> None:
        assert _patches_artifact_name(repo) == expected

    @pytest.mark.parametrize(
        ("repo", "expected"),
        [
            ("  MorpheApp/morphe-cli  ", "morphe-cli"),  # whitespace
            ("MorpheApp/morphe-cli/", "morphe-cli"),      # trailing slash
            ("  crimera/piko/  ", "piko"),                 # both
            ("/owner/repo", "repo"),                        # leading slash
        ],
    )
    def test_cli_artifact_name_trims_whitespace_and_slashes(
        self, repo: str, expected: str
    ) -> None:
        assert _cli_artifact_name(repo) == expected

    @pytest.mark.parametrize(
        ("repo", "expected"),
        [
            ("  MorpheApp/morphe-patches  ", "morphe-patches"),
            ("MorpheApp/morphe-patches/", "morphe-patches"),
            ("  crimera/piko/  ", "piko"),
        ],
    )
    def test_patches_artifact_name_trims_whitespace_and_slashes(
        self, repo: str, expected: str
    ) -> None:
        assert _patches_artifact_name(repo) == expected
