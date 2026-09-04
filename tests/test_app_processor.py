"""Tests for scripts/builder/app_processor.py."""

# ruff: noqa: S101

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest

from scripts.builder.app_processor import (
    AppBuildContext,
    AppProcessor,
    Architecture,
    DownloadSource,
    _derive_scraper_pkg_name,
    _is_morphe_patches_source,
)
from scripts.builder.cli_profiles import (
    ADOBO_CLI,
    MORPHE_CLI,
    REVANCED_CLI_V5,
    REVANCED_CLI_V6,
    CLIProfileType,
)
from scripts.builder.config import AppConfig, GlobalConfig

if TYPE_CHECKING:
    from pathlib import Path


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
    """Tests for AppProcessor._candidate_download_sources."""

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
            ({"github_dlurl": "https://github.com/owner/repo"}, DownloadSource.GITHUB),
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
        candidates = processor._candidate_download_sources(app_config)
        assert candidates[0][0] == expected_source

    def test_apkmirror_preferred_over_others(self, processor: AppProcessor) -> None:
        """APKMirror must be the first candidate whenever it's configured, regardless of dict order."""
        app_config = AppConfig(
            name="TestApp",
            options={
                "uptodown_dlurl": "https://tiktok.en.uptodown.com/android",
                "apkpure_dlurl": "https://apkpure.net/tiktok/com.zhiliaoapp.musically",
                "apkmirror_dlurl": "https://apkmirror.com/apk/tiktok-pte-ltd/tik-tok",
            },
        )
        candidates = processor._candidate_download_sources(app_config)
        assert [source for source, _ in candidates] == [
            DownloadSource.APKMIRROR,
            DownloadSource.APKPURE,
            DownloadSource.UPTODOWN,
        ]

    def test_uptodown_is_last_resort(self, processor: AppProcessor) -> None:
        """Uptodown is the least reliable source and must sort last among configured candidates."""
        app_config = AppConfig(
            name="TestApp",
            options={
                "uptodown_dlurl": "https://tiktok.en.uptodown.com/android",
                "github_dlurl": "https://github.com/owner/repo",
            },
        )
        candidates = processor._candidate_download_sources(app_config)
        assert [source for source, _ in candidates] == [DownloadSource.GITHUB, DownloadSource.UPTODOWN]


class TestDeriveScraperPkgName:
    """Tests for _derive_scraper_pkg_name."""

    def test_uptodown_uses_subdomain_not_path(self) -> None:
        """The Uptodown app slug lives in the subdomain, not the trailing '/android' path segment."""
        pkg_name = _derive_scraper_pkg_name("https://tiktok.en.uptodown.com/android", DownloadSource.UPTODOWN)
        assert pkg_name == "tiktok"

    def test_apkmirror_strips_apk_prefix(self) -> None:
        pkg_name = _derive_scraper_pkg_name("https://apkmirror.com/apk/google-inc/youtube", DownloadSource.APKMIRROR)
        assert pkg_name == "google-inc/youtube"


class TestDownloadStockApkFailover:
    """Tests for AppProcessor._download_stock_apk falling back across candidates."""

    def test_falls_through_to_second_candidate_on_failure(self, tmp_path: Path) -> None:
        download_manager = MagicMock()
        download_manager.download.side_effect = [
            RuntimeError("first source failed"),
            tmp_path,
        ]
        processor = AppProcessor(config=MagicMock(), java_runner=MagicMock(), download_manager=download_manager)
        context = AppBuildContext(
            app_name="TestApp",
            app_id="testapp",
            brand="revanced",
            version="1.0.0",
            arch="arm64-v8a",
            output_path=tmp_path / "TestApp-1.0.0-arm64-v8a.apk",
            source=DownloadSource.APKMIRROR,
            candidates=[
                (DownloadSource.APKMIRROR, "https://apkmirror.com/apk/owner/testapp"),
                (DownloadSource.APKPURE, "https://apkpure.net/testapp/com.example.testapp"),
            ],
        )

        result = processor._download_stock_apk(context)

        assert result == tmp_path
        assert download_manager.download.call_count == 2

    def test_raises_when_all_candidates_fail(self, tmp_path: Path) -> None:
        download_manager = MagicMock()
        download_manager.download.side_effect = RuntimeError("failed")
        processor = AppProcessor(config=MagicMock(), java_runner=MagicMock(), download_manager=download_manager)
        context = AppBuildContext(
            app_name="TestApp",
            app_id="testapp",
            brand="revanced",
            version="1.0.0",
            arch="arm64-v8a",
            output_path=tmp_path / "TestApp-1.0.0-arm64-v8a.apk",
            source=DownloadSource.APKMIRROR,
            candidates=[(DownloadSource.APKMIRROR, "https://apkmirror.com/apk/owner/testapp")],
        )

        with pytest.raises(RuntimeError, match="Failed to download stock APK"):
            processor._download_stock_apk(context)


class TestIsMorphePatchesSource:
    """Tests for _is_morphe_patches_source.

    Selects .mpp vs .rvp when resolving patches assets from GitHub releases
    (see _resolve_github_release_asset in app_processor.py).
    """

    @pytest.mark.parametrize(
        ("repo", "expected"),
        [
            ("MorpheApp/morphe-patches", True),
            ("MorpheApp/morphe-cli", True),
            ("someone/morphe-fork", True),
            ("wchill/rvx-morphed", True),
            ("someone/anddea-rvx-morphed", True),
            ("wchill/patcheddit", True),
            ("ReVanced/revanced-patches", False),
            ("anddea/revanced-patches", False),
            ("crimera/piko", False),
        ],
    )
    def test_is_morphe_patches_source(self, repo: str, *, expected: bool) -> None:
        assert _is_morphe_patches_source(repo) is expected


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

    def test_auto_falls_back_to_morphe_when_no_jar(self, processor: AppProcessor, tmp_path) -> None:
        processor.config.global_settings = GlobalConfig(cli_profile="auto")
        ctx = self._context(tmp_path)
        ctx.cli_jar = None
        assert processor._resolve_cli_profile(ctx) is MORPHE_CLI

    def test_auto_detects_from_jar(self, processor: AppProcessor, tmp_path, monkeypatch) -> None:
        processor.config.global_settings = GlobalConfig(cli_profile="auto")
        ctx = self._context(tmp_path)
        ctx.cli_jar = tmp_path / "fake.jar"
        assert ctx.cli_jar is not None
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
        java_runner_mock.run_jar.return_value.returncode = 0
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

    def test_morphe_profile_uses_real_morphe_desktop_flags(self, tmp_path, monkeypatch) -> None:
        """morphe-desktop's real syntax (docs/documentation.md, MorpheApp/morphe-desktop): "patch" subcommand, positional APK (no --input flag), -o/--out, -p/--patches, -d/--disable."""
        processor, java_runner = self._build_processor("morphe-cli")
        ctx = self._context(tmp_path)
        assert ctx.cli_jar is not None
        ctx.cli_jar.write_text("")

        monkeypatch.setattr(
            "scripts.builder.app_processor.detect_cli_profile",
            lambda _p: MORPHE_CLI,
        )

        stock_apk = tmp_path / "stock.apk"
        processor._run_patcher(ctx, stock_apk=stock_apk)
        call = java_runner.run_jar.call_args
        args = call.args[1]
        assert args[0] == "patch"
        assert args[-1] == str(stock_apk)
        assert "--input" not in args
        assert "-o" in args
        assert "--output" not in args
        assert "-p" in args
        assert "--patch" not in args
        assert "-d" in args
        assert "--disable" not in args
        assert "bad-patch" in args

    def test_v6_profile_uses_short_flags(self, tmp_path, monkeypatch) -> None:
        processor, java_runner = self._build_processor("revanced-cli-v6")
        ctx = self._context(tmp_path)
        assert ctx.cli_jar is not None
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

    def test_riplib_skipped_when_profile_lacks_support(self, tmp_path, monkeypatch) -> None:
        processor, java_runner = self._build_processor("auto")
        ctx = self._context(tmp_path)
        assert ctx.cli_jar is not None
        ctx.cli_jar.write_text("")
        ctx.riplib = True

        # Build a profile whose patch_args lack the RIP_LIB mapping.
        from typing import cast

        from scripts.builder.cli_profiles import ArgMapping, PatchArgs

        filtered_patch_args = cast(
            "dict[str, ArgMapping | None]",
            {k: v for k, v in REVANCED_CLI_V5.patch_args.items() if k != "RIP_LIB"},
        )
        no_rip_profile = REVANCED_CLI_V5.__class__(
            name="NoRip",
            profile_type=CLIProfileType.REVANCED_CLI_V5,
            list_patches_args=REVANCED_CLI_V5.list_patches_args,
            patch_args=PatchArgs(**filtered_patch_args),
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
