"""Tests for scripts/builder/app_processor.py."""

# ruff: noqa: S101

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from scripts.builder.app_processor import (
    AppBuildContext,
    AppProcessor,
    Architecture,
    DownloadSource,
    _cli_artifact_name,
    _patches_artifact_name,
)
from scripts.builder.cli_profiles import (
    ADOBO_CLI,
    MORPHE_CLI,
    REVANCED_CLI_V5,
    REVANCED_CLI_V6,
    CLIProfileType,
)
from scripts.builder.config import AppConfig, GlobalConfig


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


class TestResolveCliProfile:
    """Tests for AppProcessor._resolve_cli_profile (Phase 1 CLI profile fix)."""

    @pytest.fixture
    def processor(self) -> AppProcessor:
        config_mock = MagicMock()
        java_runner_mock = MagicMock()
        return AppProcessor(config=config_mock, java_runner=java_runner_mock)

    def _context(self, tmp_path) -> AppBuildContext:
        return AppBuildContext(
            app_name="app",
            app_id="app.id",
            brand="morphe",
            version="1.0",
            arch="all",
            output_path=tmp_path / "out.apk",
            source=DownloadSource.APKMIRROR,
            cli_jar=tmp_path / "cli.jar",
        )

    def test_explicit_profile_v6(self, processor: AppProcessor, tmp_path) -> None:
        processor.config.global_settings = GlobalConfig(cli_profile="revanced-cli-v6")
        ctx = self._context(tmp_path)
        assert processor._resolve_cli_profile(ctx) is REVANCED_CLI_V6

    def test_explicit_profile_v5(self, processor: AppProcessor, tmp_path) -> None:
        processor.config.global_settings = GlobalConfig(cli_profile="revanced-cli-v5")
        ctx = self._context(tmp_path)
        assert processor._resolve_cli_profile(ctx) is REVANCED_CLI_V5

    def test_explicit_profile_morphe(self, processor: AppProcessor, tmp_path) -> None:
        processor.config.global_settings = GlobalConfig(cli_profile="morphe-cli")
        ctx = self._context(tmp_path)
        assert processor._resolve_cli_profile(ctx) is MORPHE_CLI

    def test_explicit_profile_adobo(self, processor: AppProcessor, tmp_path) -> None:
        processor.config.global_settings = GlobalConfig(cli_profile="adobo-cli")
        ctx = self._context(tmp_path)
        assert processor._resolve_cli_profile(ctx) is ADOBO_CLI

    def test_auto_falls_back_to_morphe_when_no_jar(
        self, processor: AppProcessor, tmp_path
    ) -> None:
        processor.config.global_settings = GlobalConfig(cli_profile="auto")
        ctx = self._context(tmp_path)
        ctx.cli_jar = None
        assert processor._resolve_cli_profile(ctx) is MORPHE_CLI

    def test_auto_detects_from_jar(self, processor: AppProcessor, tmp_path, monkeypatch) -> None:
        processor.config.global_settings = GlobalConfig(cli_profile="auto")
        ctx = self._context(tmp_path)
        ctx.cli_jar = tmp_path / "fake.jar"
        ctx.cli_jar.write_text("")
        monkeypatch.setattr(
            "scripts.builder.app_processor.detect_cli_profile",
            lambda _p: REVANCED_CLI_V6,
        )
        assert processor._resolve_cli_profile(ctx) is REVANCED_CLI_V6

    def test_unknown_profile_falls_back_to_auto(self, processor: AppProcessor, tmp_path) -> None:
        processor.config.global_settings = GlobalConfig(cli_profile="nonsense")
        ctx = self._context(tmp_path)
        ctx.cli_jar = None
        assert processor._resolve_cli_profile(ctx) is MORPHE_CLI

    def test_profile_supports_riplib(self, processor: AppProcessor) -> None:
        assert processor._profile_supports_riplib(MORPHE_CLI) is True
        assert processor._profile_supports_riplib(REVANCED_CLI_V6) is True
        assert processor._profile_supports_riplib(REVANCED_CLI_V5) is True


class TestRunPatcherUsesProfile:
    """Regression test for Phase 1: _run_patcher must use the CLI profile."""

    def _build_processor(self, cli_profile_name: str):
        config_mock = MagicMock()
        config_mock.global_settings = GlobalConfig(cli_profile=cli_profile_name)
        java_runner_mock = MagicMock()
        return AppProcessor(config=config_mock, java_runner=java_runner_mock), java_runner_mock

    def _context(self, tmp_path) -> AppBuildContext:
        return AppBuildContext(
            app_name="app",
            app_id="app.id",
            brand="morphe",
            version="1.0",
            arch="all",
            output_path=tmp_path / "out.apk",
            source=DownloadSource.APKMIRROR,
            cli_jar=tmp_path / "cli.jar",
            patches_jars=[tmp_path / "patches.jar"],
            excluded_patches=["bad-patch"],
        )

    def test_morphe_profile_uses_long_flags(self, tmp_path, monkeypatch) -> None:
        processor, java_runner = self._build_processor("morphe-cli")
        ctx = self._context(tmp_path)
        ctx.cli_jar.write_text("")

        monkeypatch.setattr(
            "scripts.builder.app_processor.detect_cli_profile",
            lambda _p: MORPHE_CLI,
        )

        processor._run_patcher(ctx, stock_apk=tmp_path / "stock.apk")
        call = java_runner.run_jar.call_args
        args = call.args[1]
        assert "--input" in args
        assert "--output" in args
        assert "--patch" in args
        assert "--disable" in args
        assert "bad-patch" in args
        assert "-i" not in args
        assert "-d" not in args

    def test_v6_profile_uses_short_flags(self, tmp_path, monkeypatch) -> None:
        processor, java_runner = self._build_processor("revanced-cli-v6")
        ctx = self._context(tmp_path)
        ctx.cli_jar.write_text("")

        monkeypatch.setattr(
            "scripts.builder.app_processor.detect_cli_profile",
            lambda _p: REVANCED_CLI_V6,
        )

        processor._run_patcher(ctx, stock_apk=tmp_path / "stock.apk")
        call = java_runner.run_jar.call_args
        args = call.args[1]
        assert "-i" in args
        assert "-o" in args
        assert "-e" in args
        assert "-d" in args
        assert "bad-patch" in args

    def test_riplib_skipped_when_profile_lacks_support(
        self, tmp_path, monkeypatch
    ) -> None:
        processor, java_runner = self._build_processor("auto")
        ctx = self._context(tmp_path)
        ctx.cli_jar.write_text("")
        ctx.riplib = ["libfoo"]

        # Build a profile whose patch_args lack the RIP_LIB mapping.
        from scripts.builder.cli_profiles import PatchArgs

        no_rip_profile = REVANCED_CLI_V5.__class__(
            name="NoRip",
            profile_type=CLIProfileType.REVANCED_CLI_V5,
            list_patches_args=REVANCED_CLI_V5.list_patches_args,
            patch_args=PatchArgs(
                **{k: v for k, v in REVANCED_CLI_V5.patch_args.items() if k != "RIP_LIB"}
            ),
        )
        monkeypatch.setattr(
            "scripts.builder.app_processor.detect_cli_profile",
            lambda _p: no_rip_profile,
        )

        processor._run_patcher(ctx, stock_apk=tmp_path / "stock.apk")
        call = java_runner.run_jar.call_args
        args = call.args[1]
        assert "--rip-lib" not in args
        assert "-r" not in args
