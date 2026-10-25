"""Tests for scripts/builder/app_processor.py."""

# ruff: noqa: S101

from __future__ import annotations

import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast
from unittest.mock import MagicMock

import httpx
import pytest

from scripts.builder.app_processor import (
    AppBuildContext,
    AppProcessor,
    Architecture,
    BuildResult,
    DownloadSource,
    _derive_scraper_pkg_name,
    _is_morphe_patches_source,
    _resolve_github_release_asset,
)
from scripts.builder.cli_profiles import (
    ADOBO_CLI,
    MORPHE_CLI,
    CLIProfileType,
)
from scripts.builder.config import AppConfig, GlobalConfig

if TYPE_CHECKING:
    from collections.abc import Iterator


def _write_patch_output(args: list[str]) -> None:
    if args and args[0] == "patch":
        Path(args[args.index("-o") + 1]).write_bytes(b"patched")


def _fake_patch_run(_jar: str, args: list[str], **_kwargs: object) -> MagicMock:
    _write_patch_output(args)
    return MagicMock(returncode=0, stdout="", stderr="")


class TestAppProcessorArchitecture:
    """Tests for AppProcessor._parse_architecture."""

    @pytest.fixture
    def processor(self) -> AppProcessor:
        """Provide a mocked AppProcessor instance."""
        config_mock = MagicMock()
        config_mock.global_settings = GlobalConfig()
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

    def test_armeabi_v7a_alias(self, processor: AppProcessor) -> None:
        """build.yml offers the real ABI name, which must map to the enum's arm-v7a."""
        config = AppConfig(name="TestApp", options={"arch": "armeabi-v7a"})
        assert processor._parse_architecture(config) == Architecture.ARM_V7A

    def test_global_arch_fallback(self, processor: AppProcessor) -> None:
        processor.config.global_settings = GlobalConfig(arch="arm64-v8a")
        config = AppConfig(name="TestApp", options={})
        assert processor._parse_architecture(config) == Architecture.ARM64_V8A

    def test_app_arch_overrides_global(self, processor: AppProcessor) -> None:
        processor.config.global_settings = GlobalConfig(arch="arm64-v8a")
        config = AppConfig(name="TestApp", options={"arch": "both"})
        assert processor._parse_architecture(config) == Architecture.BOTH

    def test_invalid_arch_fails_only_that_app(self, processor: AppProcessor, tmp_path: Path) -> None:
        good = AppConfig(name="Good", options={"arch": "arm64-v8a"})
        bad = AppConfig(name="Bad", options={"arch": "mips"})
        processor.config.apps = {"Bad": bad, "Good": good}
        processor.config.global_settings = GlobalConfig(parallel_jobs=1)
        processor._get_keystore_path = MagicMock(return_value=None)
        built: list[tuple[str, str]] = []

        def fake_build(app_config: AppConfig, arch: str) -> BuildResult:
            built.append((app_config.name, arch))
            return BuildResult(app_config.name, "b", "1", arch, tmp_path, success=True)

        processor._build_app_variant = MagicMock(side_effect=fake_build)

        summary = processor.process_all()

        assert built == [("Good", "arm64-v8a")]
        assert [r.app_name for r in summary.succeeded] == ["Good"]
        assert [r.app_name for r in summary.failed] == ["Bad"]
        assert "Invalid architecture: mips" in (summary.failed[0].error or "")


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

        # Stock download must never land under the build/output directory --
        # it would get swept up by the `build/*.apk` artifact/release glob.
        call_output_path = download_manager.download.call_args_list[0].args[2]
        assert call_output_path.parent != context.output_path.parent

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

    def test_stock_path_includes_arch(self, tmp_path: Path) -> None:
        """Parallel arch variants of one app must not overwrite each other's stock APK."""
        download_manager = MagicMock()
        download_manager.download.return_value = tmp_path
        processor = AppProcessor(config=MagicMock(), java_runner=MagicMock(), download_manager=download_manager)
        paths = []
        for arch in ("arm64-v8a", "arm-v7a"):
            context = AppBuildContext(
                app_name="TestApp",
                app_id="testapp",
                brand="revanced",
                version="1.0.0",
                arch=arch,
                output_path=tmp_path / f"TestApp-1.0.0-{arch}.apk",
                source=DownloadSource.APKMIRROR,
                candidates=[(DownloadSource.APKMIRROR, "https://apkmirror.com/apk/owner/testapp")],
            )
            processor._download_stock_apk(context)
            paths.append(download_manager.download.call_args.args[2])

        assert paths[0].name == "stock-TestApp-1.0.0-arm64-v8a.apk"
        assert paths[1].name == "stock-TestApp-1.0.0-arm-v7a.apk"

    def test_no_download_manager_raises(self, tmp_path: Path) -> None:
        processor = AppProcessor(config=MagicMock(), java_runner=MagicMock())
        context = AppBuildContext(
            app_name="TestApp",
            app_id="testapp",
            brand="revanced",
            version="1.0.0",
            arch="arm64-v8a",
            output_path=tmp_path / "out.apk",
            source=DownloadSource.APKMIRROR,
            download_url="https://apkmirror.com/apk/owner/testapp",
        )
        with pytest.raises(RuntimeError, match="No download manager configured"):
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
            lambda _p: ADOBO_CLI,
        )
        assert processor._resolve_cli_profile(ctx) is ADOBO_CLI

    def test_unknown_profile_falls_back_to_auto(self, processor: AppProcessor, tmp_path) -> None:
        processor.config.global_settings = GlobalConfig(cli_profile="nonsense")
        ctx = self._context(tmp_path)
        ctx.cli_jar = None
        assert processor._resolve_cli_profile(ctx) is MORPHE_CLI

    def test_profile_supports_riplib(self, processor: AppProcessor) -> None:
        assert processor._profile_supports_riplib(MORPHE_CLI) is True
        assert processor._profile_supports_riplib(ADOBO_CLI) is True


class TestRunPatcherUsesProfile:
    """Regression test for Phase 1: _run_patcher must use the CLI profile."""

    def _build_processor(self, cli_profile_name: str):
        config_mock = MagicMock()
        config_mock.global_settings = GlobalConfig(cli_profile=cli_profile_name)
        java_runner_mock = MagicMock()
        java_runner_mock.run_jar.side_effect = _fake_patch_run
        processor = AppProcessor(config=config_mock, java_runner=java_runner_mock)
        processor._source_keystore_path = MagicMock(return_value=None)
        return processor, java_runner_mock

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
            {k: v for k, v in MORPHE_CLI.patch_args.items() if k != "RIP_LIB"},
        )
        no_rip_profile = MORPHE_CLI.__class__(
            name="NoRip",
            profile_type=CLIProfileType.MORPHE_CLI,
            list_patches_args=MORPHE_CLI.list_patches_args,
            patch_args=PatchArgs(**filtered_patch_args),
        )
        monkeypatch.setattr(
            "scripts.builder.app_processor.detect_cli_profile",
            lambda _p: no_rip_profile,
        )

        processor._run_patcher(ctx, stock_apk=tmp_path / "stock.apk")
        call = java_runner.run_jar.call_args
        args = call.args[1]
        assert "--striplibs" not in args


def _release(tag: str, *assets: str, draft: bool = False, prerelease: bool = False) -> dict[str, Any]:
    return {
        "tag_name": tag,
        "draft": draft,
        "prerelease": prerelease,
        "assets": [{"name": name, "url": f"https://api.github.com/assets/{tag}/{name}"} for name in assets],
    }


def _not_found(url: str) -> httpx.HTTPStatusError:
    request = httpx.Request("GET", url)
    return httpx.HTTPStatusError("404", request=request, response=httpx.Response(404, request=request))


@pytest.fixture
def fake_github(monkeypatch: pytest.MonkeyPatch) -> Iterator[dict[str, Any]]:
    """Route gh_req/gh_dl to in-memory release data; gh_dl mimics 'existing file means success'."""
    _resolve_github_release_asset.cache_clear()
    state: dict[str, Any] = {"responses": {}, "requests": [], "downloads": []}

    def fake_gh_req(url: str, *_args: object, **_kwargs: object) -> str:
        state["requests"].append(url)
        if url not in state["responses"]:
            raise _not_found(url)
        return json.dumps(state["responses"][url])

    def fake_gh_dl(asset_path: str | Path, url: str, *_args: object, **_kwargs: object) -> bool:
        target = Path(asset_path)
        if target.exists():
            return True
        state["downloads"].append((target.name, url))
        target.write_bytes(b"jar")
        return True

    monkeypatch.setattr("scripts.utils.network.gh_req", fake_gh_req)
    monkeypatch.setattr("scripts.utils.network.gh_dl", fake_gh_dl)
    yield state
    _resolve_github_release_asset.cache_clear()


_API = "https://api.github.com/repos"


class TestResolveGithubReleaseAsset:
    def test_draft_and_prerelease_are_skipped_for_latest(self, fake_github: dict[str, Any]) -> None:
        fake_github["responses"][f"{_API}/o/r/releases"] = [
            _release("v3", "cli-3.jar", draft=True),
            _release("v2", "cli-2.jar", prerelease=True),
            _release("v1", "cli-1.jar"),
        ]
        assert _resolve_github_release_asset("o/r", "jar")[::2] == ("cli-1.jar", "v1")

    def test_dev_accepts_prerelease_but_not_draft(self, fake_github: dict[str, Any]) -> None:
        fake_github["responses"][f"{_API}/o/r/releases"] = [
            _release("v3", "cli-3.jar", draft=True),
            _release("v2", "cli-2.jar", prerelease=True),
        ]
        assert _resolve_github_release_asset("o/r", "jar", version="dev")[2] == "v2"

    def test_walks_past_release_without_asset(self, fake_github: dict[str, Any]) -> None:
        fake_github["responses"][f"{_API}/o/r/releases"] = [
            _release("v2", "notes.txt"),
            _release("v1", "patches-1.rvp"),
        ]
        name, _url, tag = _resolve_github_release_asset("o/r", "mpp", "rvp")
        assert (name, tag) == ("patches-1.rvp", "v1")

    def test_no_matching_asset_raises(self, fake_github: dict[str, Any]) -> None:
        fake_github["responses"][f"{_API}/o/r/releases"] = [_release("v1", "notes.txt")]
        with pytest.raises(RuntimeError, match=r"No \.jar asset"):
            _resolve_github_release_asset("o/r", "jar")

    def test_pinned_version_uses_tags_with_v_fallback(self, fake_github: dict[str, Any]) -> None:
        fake_github["responses"][f"{_API}/o/r/releases/tags/v1.2.0"] = _release("v1.2.0", "cli.jar")
        name, _url, tag = _resolve_github_release_asset("o/r", "jar", version="1.2.0")
        assert (name, tag) == ("cli.jar", "v1.2.0")
        assert fake_github["requests"] == [f"{_API}/o/r/releases/tags/1.2.0", f"{_API}/o/r/releases/tags/v1.2.0"]

    def test_result_is_cached(self, fake_github: dict[str, Any]) -> None:
        fake_github["responses"][f"{_API}/o/r/releases"] = [_release("v1", "cli.jar")]
        _resolve_github_release_asset("o/r", "jar")
        _resolve_github_release_asset("o/r", "jar")
        assert len(fake_github["requests"]) == 1


class TestEnsurePrebuilts:
    def _processor(self, *, use_cache: bool = True) -> AppProcessor:
        config = MagicMock()
        config.global_settings = GlobalConfig(use_cache=use_cache)
        return AppProcessor(config=config, java_runner=MagicMock())

    def _context(self, tmp_path: Path, patches_source: str | list[str]) -> AppBuildContext:
        return AppBuildContext(
            app_name="App",
            app_id="App",
            brand="b",
            version="1.0",
            arch="arm64-v8a",
            output_path=tmp_path / "out.apk",
            source=DownloadSource.APKMIRROR,
            cli_source="MorpheApp/morphe-cli",
            patches_source=patches_source,
        )

    @pytest.fixture(autouse=True)
    def _cache_dir(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("CACHE_DIR", str(tmp_path))

    def _seed(self, fake_github: dict[str, Any]) -> None:
        fake_github["responses"][f"{_API}/MorpheApp/morphe-cli/releases"] = [_release("v1.0", "morphe-all.jar")]
        fake_github["responses"][f"{_API}/a/morphe-patches/releases"] = [_release("v5", "patches.mpp")]
        fake_github["responses"][f"{_API}/b/morphe-patches/releases"] = [_release("v5", "patches.mpp")]

    def test_files_are_keyed_by_repo_and_tag(self, tmp_path: Path, fake_github: dict[str, Any]) -> None:
        self._seed(fake_github)
        ctx = self._context(tmp_path, ["a/morphe-patches", "b/morphe-patches"])

        cli_jar, patches = self._processor()._ensure_prebuilts(ctx)

        assert cli_jar.name == "MorpheApp-morphe-cli-v1.0.jar"
        assert [p.name for p in patches] == ["a-morphe-patches-v5.mpp", "b-morphe-patches-v5.mpp"]
        assert len(fake_github["downloads"]) == 3

    def test_cached_files_are_reused(self, tmp_path: Path, fake_github: dict[str, Any]) -> None:
        self._seed(fake_github)
        ctx = self._context(tmp_path, "a/morphe-patches")
        self._processor()._ensure_prebuilts(ctx)
        self._processor()._ensure_prebuilts(ctx)
        assert len(fake_github["downloads"]) == 2

    def test_use_cache_false_downloads_again_once_per_run(self, tmp_path: Path, fake_github: dict[str, Any]) -> None:
        self._seed(fake_github)
        ctx = self._context(tmp_path, "a/morphe-patches")
        self._processor()._ensure_prebuilts(ctx)

        processor = self._processor(use_cache=False)
        processor._ensure_prebuilts(ctx)
        processor._ensure_prebuilts(ctx)

        assert len(fake_github["downloads"]) == 4

    def test_patches_version_is_pinned(self, tmp_path: Path, fake_github: dict[str, Any]) -> None:
        self._seed(fake_github)
        fake_github["responses"][f"{_API}/a/morphe-patches/releases/tags/v4"] = _release("v4", "old.mpp")
        ctx = self._context(tmp_path, "a/morphe-patches")
        ctx.patches_version = "v4"

        _cli, patches = self._processor()._ensure_prebuilts(ctx)

        assert patches[0].name == "a-morphe-patches-v4.mpp"


class TestResolveVersion:
    def _setup(
        self, tmp_path: Path, version: str, candidates: list[tuple[DownloadSource, str]], options: dict[str, Any]
    ) -> tuple[AppProcessor, MagicMock, MagicMock, AppBuildContext]:
        resolver = MagicMock()
        resolver.resolve.return_value = ("1.2.3", "1.2.3")
        java_runner = MagicMock()
        java_runner.run_jar.return_value = MagicMock(returncode=0, stdout="1.2.3 (10 patches)\n1.2.0\n", stderr="")
        processor = AppProcessor(config=MagicMock(), java_runner=java_runner, version_resolver=resolver)
        ctx = AppBuildContext(
            app_name="App",
            app_id="App",
            brand="b",
            version=version,
            arch="arm64-v8a",
            output_path=Path("build") / f"App-{version}-arm64-v8a.apk",
            source=candidates[0][0],
            download_url=candidates[0][1],
            cli_jar=tmp_path / "cli.jar",
            patches_jars=[tmp_path / "a.mpp", tmp_path / "b.mpp"],
            options=options,
            candidates=candidates,
        )
        return processor, resolver, java_runner, ctx

    _MIRROR = (DownloadSource.APKMIRROR, "https://apkmirror.com/apk/owner/app")

    def test_auto_passes_parsed_list_and_renames_output(self, tmp_path: Path) -> None:
        processor, resolver, java_runner, ctx = self._setup(
            tmp_path, "auto", [self._MIRROR], {"package_name": "com.example.app"}
        )

        processor._resolve_version(ctx)

        assert java_runner.run_jar.call_args.args[1] == [
            "list-versions",
            "--patches",
            str(tmp_path / "a.mpp"),
            "--patches",
            str(tmp_path / "b.mpp"),
            "-f",
            "com.example.app",
        ]
        assert resolver.resolve.call_args.kwargs == {"compatible": ["1.2.3", "1.2.0"], "include_beta": False}
        assert ctx.version == "1.2.3"
        assert ctx.output_path == Path("build") / "App-1.2.3-arm64-v8a.apk"

    def test_auto_derives_package_from_apkpure_url(self, tmp_path: Path) -> None:
        apkpure = (DownloadSource.APKPURE, "https://apkpure.net/youtube/com.google.android.youtube")
        processor, _resolver, java_runner, ctx = self._setup(tmp_path, "auto", [self._MIRROR, apkpure], {})

        processor._resolve_version(ctx)

        assert java_runner.run_jar.call_args.args[1][-2:] == ["-f", "com.google.android.youtube"]

    def test_list_versions_failure_raises(self, tmp_path: Path) -> None:
        processor, _resolver, java_runner, ctx = self._setup(tmp_path, "auto", [self._MIRROR], {"package_name": "x"})
        java_runner.run_jar.return_value = MagicMock(returncode=1, stdout="", stderr="boom")
        with pytest.raises(RuntimeError, match="list-versions failed"):
            processor._resolve_version(ctx)

    def test_missing_package_gives_empty_compatible(self, tmp_path: Path) -> None:
        processor, resolver, java_runner, ctx = self._setup(tmp_path, "auto", [self._MIRROR], {})

        processor._resolve_version(ctx)

        java_runner.run_jar.assert_not_called()
        assert resolver.resolve.call_args.kwargs["compatible"] == []

    def test_latest_passes_empty_compatible(self, tmp_path: Path) -> None:
        processor, resolver, java_runner, ctx = self._setup(tmp_path, "latest", [self._MIRROR], {"package_name": "x"})

        processor._resolve_version(ctx)

        java_runner.run_jar.assert_not_called()
        assert resolver.resolve.call_args.kwargs == {"compatible": [], "include_beta": False}

    def test_beta_sets_include_beta(self, tmp_path: Path) -> None:
        processor, resolver, _java_runner, ctx = self._setup(tmp_path, "beta", [self._MIRROR], {})

        processor._resolve_version(ctx)

        assert resolver.resolve.call_args.kwargs == {"compatible": [], "include_beta": True}

    def test_pinned_version_calls_nothing(self, tmp_path: Path) -> None:
        processor, resolver, java_runner, ctx = self._setup(tmp_path, "19.0.1", [self._MIRROR], {})

        processor._resolve_version(ctx)

        resolver.resolve.assert_not_called()
        java_runner.run_jar.assert_not_called()
        assert ctx.version == "19.0.1"

    def test_failover_reorders_candidates(self, tmp_path: Path) -> None:
        apkpure = (DownloadSource.APKPURE, "https://apkpure.net/app/com.example.app")
        processor, resolver, _java_runner, ctx = self._setup(tmp_path, "latest", [self._MIRROR, apkpure], {})
        resolver.resolve.side_effect = [ValueError("no patch-compatible version"), ("2.0", "2.0")]

        processor._resolve_version(ctx)

        assert ctx.version == "2.0"
        assert ctx.candidates == [apkpure, self._MIRROR]
        assert ctx.source == DownloadSource.APKPURE


_LIST_PATCHES = {
    "a.mpp": "Name: From A\nName: Shared\n",
    "b.mpp": "INFO: Name: From B\nName: Shared\n",
}


class TestPerBundlePatchFlags:
    def _processor(self) -> tuple[AppProcessor, MagicMock]:
        config = MagicMock()
        config.global_settings = GlobalConfig(cli_profile="morphe-cli")
        java_runner = MagicMock()

        def fake_run_jar(_jar: str, args: list[str], **_kwargs: object) -> MagicMock:
            if args[0] == "list-patches":
                return MagicMock(returncode=0, stdout=_LIST_PATCHES[Path(args[2]).name], stderr="")
            return _fake_patch_run(_jar, args)

        java_runner.run_jar.side_effect = fake_run_jar
        processor = AppProcessor(config=config, java_runner=java_runner)
        processor._source_keystore_path = MagicMock(return_value=None)
        return processor, java_runner

    def _context(self, tmp_path: Path, *, exclusive: bool) -> AppBuildContext:
        return AppBuildContext(
            app_name="App",
            app_id="App",
            brand="b",
            version="1.0",
            arch="arm64-v8a",
            output_path=tmp_path / "out.apk",
            source=DownloadSource.APKMIRROR,
            cli_jar=tmp_path / "cli.jar",
            patches_jars=[tmp_path / "a.mpp", tmp_path / "b.mpp"],
            included_patches=["From A", "Shared", "From B"],
            excluded_patches=["Gone"],
            exclusive_patches=exclusive,
            riplib=False,
            patch_options={"From A": {"k": "v"}},
        )

    def test_flags_follow_their_bundle(self, tmp_path: Path) -> None:
        processor, java_runner = self._processor()
        ctx = self._context(tmp_path, exclusive=True)

        ctx.bundle_patch_names = processor._bundle_patch_names(ctx, MORPHE_CLI)
        processor._run_patcher(ctx, tmp_path / "stock.apk")

        list_calls = [c.args[1] for c in java_runner.run_jar.call_args_list if c.args[1][0] == "list-patches"]
        assert list_calls == [
            ["list-patches", "--patches", str(tmp_path / "a.mpp"), "-u"],
            ["list-patches", "--patches", str(tmp_path / "b.mpp"), "-u"],
        ]
        args = java_runner.run_jar.call_args.args[1]
        a_idx, b_idx = args.index(str(tmp_path / "a.mpp")), args.index(str(tmp_path / "b.mpp"))
        assert a_idx < args.index("From A") < b_idx
        assert args[args.index("From A") + 1 : args.index("From A") + 3] == ["-O", "k=v"]
        # Later bundle wins for a name both bundles list; unknown names go to the last bundle.
        assert args.index("Shared") > b_idx
        assert args.index("From B") > b_idx
        assert args.index("Gone") > b_idx

    def test_changelog_exclusive_lists_found_includes(self, tmp_path: Path) -> None:
        processor, _java_runner = self._processor()
        ctx = self._context(tmp_path, exclusive=True)
        ctx.included_patches = ["From A", "Missing"]
        ctx.bundle_patch_names = processor._bundle_patch_names(ctx, MORPHE_CLI)

        assert processor._get_changelog(ctx) == ["From A"]

    def test_changelog_non_exclusive_lists_all_minus_excluded(self, tmp_path: Path) -> None:
        processor, _java_runner = self._processor()
        ctx = self._context(tmp_path, exclusive=False)
        ctx.excluded_patches = ["Shared"]
        ctx.bundle_patch_names = processor._bundle_patch_names(ctx, MORPHE_CLI)

        assert processor._get_changelog(ctx) == ["From A", "From B"]

    def test_list_failure_in_multi_bundle_app_fails_variant(self, tmp_path: Path) -> None:
        """A missing list would push that bundle's -e flags onto the last bundle, silently dropping patches."""
        processor, java_runner = self._processor()
        java_runner.run_jar.side_effect = [
            MagicMock(returncode=0, stdout="Name: From A\n", stderr=""),
            subprocess.TimeoutExpired("java", 120),
        ]
        ctx = self._context(tmp_path, exclusive=False)

        with pytest.raises(RuntimeError, match=r"Cannot map patches to bundles: b\.mpp"):
            processor._bundle_patch_names(ctx, MORPHE_CLI)

    def test_list_failure_single_bundle_gives_empty_names(self, tmp_path: Path) -> None:
        processor, java_runner = self._processor()
        java_runner.run_jar.side_effect = RuntimeError("java missing")
        ctx = self._context(tmp_path, exclusive=False)
        ctx.patches_jars = [tmp_path / "a.mpp"]

        assert processor._bundle_patch_names(ctx, MORPHE_CLI) == [[]]

    def test_list_patches_timeout_is_120s(self, tmp_path: Path) -> None:
        processor, java_runner = self._processor()
        ctx = self._context(tmp_path, exclusive=False)

        processor._bundle_patch_names(ctx, MORPHE_CLI)

        assert {c.kwargs["timeout"] for c in java_runner.run_jar.call_args_list} == {120}

    def test_unknown_included_patch_is_warned(self, tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
        processor, _java_runner = self._processor()
        ctx = self._context(tmp_path, exclusive=True)
        ctx.included_patches = ["From A", "Typo Patch"]

        processor._bundle_patch_names(ctx, MORPHE_CLI)

        assert "Typo Patch" in caplog.text
        assert "'From A'" not in caplog.text


class TestResign:
    def _setup(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *, sign_ok: bool
    ) -> tuple[AppProcessor, AppBuildContext, list[tuple[Any, ...]]]:
        monkeypatch.setenv("KEYSTORE_PASSWORD", "storepw")
        monkeypatch.setenv("KEYSTORE_ENTRY_PASSWORD", "keypw")
        source_ks = tmp_path / "ks.keystore"
        source_ks.write_bytes(b"ks")
        bks = tmp_path / "converted.bks"
        monkeypatch.setattr("scripts.utils.keystore.ensure_bks", lambda *_a, **_k: bks)
        calls: list[tuple[Any, ...]] = []

        def fake_sign(*args: Path | str) -> bool:
            calls.append(args)
            if sign_ok:
                Path(args[1]).write_bytes(b"signed")
            return sign_ok

        monkeypatch.setattr("scripts.utils.apk.sign_apk", fake_sign)

        config = MagicMock()
        config.global_settings = GlobalConfig(cli_profile="morphe-cli", keystore_path=str(source_ks))
        java_runner = MagicMock()
        java_runner.run_jar.side_effect = _fake_patch_run
        processor = AppProcessor(config=config, java_runner=java_runner)
        ctx = AppBuildContext(
            app_name="App",
            app_id="App",
            brand="b",
            version="1.0",
            arch="arm64-v8a",
            output_path=tmp_path / "out.apk",
            source=DownloadSource.APKMIRROR,
            cli_jar=tmp_path / "cli.jar",
            patches_jars=[tmp_path / "a.mpp"],
        )
        return processor, ctx, calls

    def test_output_is_resigned_v1_v2(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        processor, ctx, calls = self._setup(tmp_path, monkeypatch, sign_ok=True)

        result = processor._run_patcher(ctx, tmp_path / "stock.apk")

        patch_args = cast("MagicMock", processor.java_runner.run_jar).call_args.args[1]
        assert patch_args[patch_args.index("--keystore") + 1] == str(tmp_path / "converted.bks")
        unsigned, signed, *rest = calls[0]
        assert rest == [tmp_path / "ks.keystore", "storepw", "morphe", "keypw"]
        assert (unsigned.name, signed.name) == ("out.apk", "out.signed.apk")
        assert unsigned.parent == signed.parent != tmp_path
        assert patch_args[patch_args.index("-o") + 1] == str(unsigned)
        assert result == ctx.output_path
        assert result.read_bytes() == b"signed"
        assert sorted(p.name for p in tmp_path.glob("*.apk")) == ["out.apk"]
        assert not unsigned.parent.exists()

    def test_resign_failure_raises(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        processor, ctx, _calls = self._setup(tmp_path, monkeypatch, sign_ok=False)

        with pytest.raises(RuntimeError, match=r"Re-signing out.apk"):
            processor._run_patcher(ctx, tmp_path / "stock.apk")


class TestKeystoreCredentials:
    def _processor(self) -> AppProcessor:
        config = MagicMock()
        config.global_settings = GlobalConfig()
        return AppProcessor(config=config, java_runner=MagicMock())

    def test_entry_password_defaults_to_store_password(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("KEYSTORE_PASSWORD", "storepw")
        monkeypatch.setenv("KEYSTORE_ENTRY_PASSWORD", "")
        _alias, store, entry, _signer = self._processor()._get_keystore_credentials()
        assert (store, entry) == ("storepw", "storepw")

    def test_explicit_entry_password_wins(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("KEYSTORE_PASSWORD", "storepw")
        monkeypatch.setenv("KEYSTORE_ENTRY_PASSWORD", "keypw")
        _alias, store, entry, _signer = self._processor()._get_keystore_credentials()
        assert (store, entry) == ("storepw", "keypw")

    def test_both_unset_use_default(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("KEYSTORE_PASSWORD", raising=False)
        monkeypatch.delenv("KEYSTORE_ENTRY_PASSWORD", raising=False)
        _alias, store, entry, _signer = self._processor()._get_keystore_credentials()
        assert (store, entry) == ("Morphe", "Morphe")


class TestKeystoreFailure:
    def test_keystore_error_fails_every_app_and_still_writes_build_log(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from scripts.builder import app_processor
        from scripts.builder.config import Config as BuilderConfig

        monkeypatch.chdir(tmp_path)
        config = BuilderConfig(
            global_settings=GlobalConfig(keystore_path=str(tmp_path / "missing.keystore")),
            apps={"A": AppConfig(name="A"), "B": AppConfig(name="B"), "Off": AppConfig(name="Off", enabled=False)},
            modules={},
            source_files=[],
            loaded_at=datetime.now(UTC),
        )

        def boom(*_args: object, **_kwargs: object) -> Path:
            msg = "keytool not found"
            raise FileNotFoundError(msg)

        monkeypatch.setattr("scripts.utils.keystore.ensure_bks", boom)
        monkeypatch.setattr("scripts.scrapers.download_manager.DownloadManager", MagicMock)

        assert app_processor.run(config) == 1

        build_md = (tmp_path / "build.md").read_text(encoding="utf-8")
        assert "- A: Keystore preparation failed: keytool not found" in build_md
        assert "- B: Keystore preparation failed: keytool not found" in build_md
        assert "Off" not in build_md


class TestCompatibleFallback:
    def _setup(self, tmp_path: Path) -> tuple[AppProcessor, MagicMock, AppBuildContext]:
        resolver = MagicMock()
        java_runner = MagicMock()
        java_runner.run_jar.return_value = MagicMock(returncode=0, stdout="1.0.0\n", stderr="")
        processor = AppProcessor(config=MagicMock(), java_runner=java_runner, version_resolver=resolver)
        candidates = [
            (DownloadSource.APKMIRROR, "https://apkmirror.com/apk/owner/app"),
            (DownloadSource.APKPURE, "https://apkpure.net/app/com.example.app"),
        ]
        ctx = AppBuildContext(
            app_name="App",
            app_id="App",
            brand="b",
            version="auto",
            arch="arm64-v8a",
            output_path=tmp_path / "out.apk",
            source=candidates[0][0],
            download_url=candidates[0][1],
            cli_jar=tmp_path / "cli.jar",
            patches_jars=[tmp_path / "a.mpp"],
            candidates=candidates,
        )
        return processor, resolver, ctx

    def test_falls_back_to_newest_when_no_source_has_compatible(self, tmp_path: Path) -> None:
        processor, resolver, ctx = self._setup(tmp_path)
        resolver.resolve.side_effect = [
            ValueError("no patch-compatible version on apkmirror"),
            ValueError("no patch-compatible version on apkpure"),
            ("9.9.9", "9.9.9"),
        ]

        processor._resolve_version(ctx)

        kwargs = [c.kwargs["compatible"] for c in resolver.resolve.call_args_list]
        assert kwargs == [["1.0.0"], ["1.0.0"], []]
        assert ctx.version == "9.9.9"

    def test_compatible_on_second_source_is_preferred(self, tmp_path: Path) -> None:
        processor, resolver, ctx = self._setup(tmp_path)
        resolver.resolve.side_effect = [ValueError("no patch-compatible version on apkmirror"), ("1.0.0", "1.0.0")]

        processor._resolve_version(ctx)

        assert ctx.version == "1.0.0"
        assert resolver.resolve.call_count == 2
        assert ctx.source == DownloadSource.APKPURE

    @pytest.mark.parametrize(
        "unusable",
        [
            RuntimeError("HTTP 403 for https://apkpure.net/app/com.example.app/versions"),
            ValueError("No versions found for 'app' on uptodown"),
        ],
    )
    def test_unusable_source_does_not_block_fallback(self, tmp_path: Path, unusable: Exception) -> None:
        processor, resolver, ctx = self._setup(tmp_path)
        resolver.resolve.side_effect = [
            ValueError("no patch-compatible version on apkmirror"),
            unusable,
            ("9.9.9", "9.9.9"),
        ]

        processor._resolve_version(ctx)

        assert ctx.version == "9.9.9"
        assert resolver.resolve.call_args_list[-1].kwargs["compatible"] == []

    def test_other_errors_do_not_trigger_fallback(self, tmp_path: Path) -> None:
        processor, resolver, ctx = self._setup(tmp_path)
        resolver.resolve.side_effect = [
            ValueError("no patch-compatible version on apkmirror"),
            RuntimeError("HTTP 503"),
        ]

        with pytest.raises(RuntimeError, match="Failed to resolve version"):
            processor._resolve_version(ctx)
        assert resolver.resolve.call_count == 2
