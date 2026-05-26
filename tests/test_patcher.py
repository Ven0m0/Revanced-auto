"""Tests for the patcher module."""

# ruff: noqa: S101
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from scripts.builder.cli_profiles import (
    ADOBO_CLI,
    MORPHE_CLI,
    REVANCED_CLI_V5,
    REVANCED_CLI_V6,
    CLIProfile,
)
from scripts.builder.config import AppConfig
from scripts.builder.patcher import (
    CacheManager,
    PatcherConfig,
    ReVancedPatcher,
)
from scripts.utils.java import JavaRunner


@pytest.fixture
def patcher(tmp_path: Path) -> ReVancedPatcher:
    config_mock = MagicMock(spec=AppConfig)
    cli_profile_mock = MagicMock(spec=CLIProfile)
    java_runner_mock = MagicMock(spec=JavaRunner)
    java_runner_mock.java_args = ["-Xmx2G"]

    patcher_config = PatcherConfig(
        keystore_path=tmp_path / "keystore.jks",
        keystore_password="dummy_password",  # noqa: S106
        key_alias="alias",
        key_password="dummy_password",  # noqa: S106
    )

    cache_manager = CacheManager(cache_dir=tmp_path / "cache")

    return ReVancedPatcher(
        config=config_mock,
        cli_profile=cli_profile_mock,
        java_runner=java_runner_mock,
        patcher_config=patcher_config,
        cache_manager=cache_manager,
    )


def test_get_cached_patches_list_read_text_oserror(patcher: ReVancedPatcher, tmp_path: Path) -> None:
    """Test fallback to generating patch list when reading cache raises OSError."""
    cli_jar = tmp_path / "cli.jar"
    cli_jar.write_bytes(b"cli")

    patches_jar = tmp_path / "patches.jar"
    patches_jar.write_bytes(b"patches")

    with (
        patch("scripts.builder.patcher._get_file_hash") as mock_hash,
        patch("scripts.builder.patcher.subprocess.run") as mock_run,
        patch.object(patcher._cache_manager, "cache_is_valid", return_value=True),
        patch("pathlib.Path.read_text", side_effect=OSError("Permission denied")),
    ):
        mock_hash.side_effect = ["hash1", "hash2"]
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = "generated patches"
        mock_run.return_value.stderr = ""

        result = patcher.get_cached_patches_list(cli_jar, [patches_jar])

        assert result == "generated patches"
        mock_run.assert_called_once()


def test_get_cached_patches_list_read_text_success(patcher: ReVancedPatcher, tmp_path: Path) -> None:
    """Test successful read of cached patch list."""
    cli_jar = tmp_path / "cli.jar"
    cli_jar.write_bytes(b"cli")

    patches_jar = tmp_path / "patches.jar"
    patches_jar.write_bytes(b"patches")

    with (
        patch("scripts.builder.patcher._get_file_hash") as mock_hash,
        patch("scripts.builder.patcher.subprocess.run") as mock_run,
        patch.object(patcher._cache_manager, "cache_is_valid", return_value=True),
        patch("pathlib.Path.read_text", return_value="cached patches"),
    ):
        mock_hash.side_effect = ["hash1", "hash2"]

        result = patcher.get_cached_patches_list(cli_jar, [patches_jar])

        assert result == "cached patches"
        mock_run.assert_not_called()


def _make_patcher(tmp_path: Path, profile: CLIProfile) -> ReVancedPatcher:
    java_runner_mock = MagicMock(spec=JavaRunner)
    java_runner_mock.java_args = ["-Xmx2G"]
    patcher_config = PatcherConfig(
        keystore_path=tmp_path / "ks.jks",
        keystore_password="pw",  # noqa: S106
        key_alias="alias",
        key_password="pw",  # noqa: S106
    )
    return ReVancedPatcher(
        config=MagicMock(spec=AppConfig),
        cli_profile=profile,
        java_runner=java_runner_mock,
        patcher_config=patcher_config,
        cache_manager=CacheManager(cache_dir=tmp_path / "cache"),
    )


@pytest.mark.parametrize("profile", [REVANCED_CLI_V5, REVANCED_CLI_V6, MORPHE_CLI, ADOBO_CLI])
def test_build_patch_args_delegates_to_profile(profile: CLIProfile, tmp_path: Path) -> None:
    """_build_patch_args should produce profile-appropriate flags plus signing extras."""
    p = _make_patcher(tmp_path, profile)
    stock = tmp_path / "in.apk"
    out = tmp_path / "out.apk"
    pjar = tmp_path / "patches.jar"

    args = p._build_patch_args(
        stock_apk=stock,
        output_apk=out,
        patches_jars=[pjar],
        exclude_patches=["X"],
        include_patches=["Y"],
        merge_jars=[],
        patches_post=[],
        force=True,
    )

    # Profile-driven content: input, output, patches jar, exclude, include all appear.
    assert str(stock) in args
    assert str(out) in args
    assert str(pjar) in args
    assert "X" in args
    assert "Y" in args
    # Signing extras are always appended regardless of profile.
    assert "--keystore-password=env:RV_KEYSTORE_PASSWORD" in args
    assert "--keystore-entry-password=env:RV_KEYSTORE_ENTRY_PASSWORD" in args
    assert "--signer" in args
    assert "alias" in args
    assert "--keystore-entry-alias" in args


def test_build_patch_args_v6_uses_short_flags(tmp_path: Path) -> None:
    p = _make_patcher(tmp_path, REVANCED_CLI_V6)
    args = p._build_patch_args(
        stock_apk=tmp_path / "in.apk",
        output_apk=tmp_path / "out.apk",
        patches_jars=[tmp_path / "p.jar"],
        exclude_patches=[],
        include_patches=[],
        merge_jars=[],
        patches_post=[],
        force=False,
    )
    assert "-i" in args
    assert "-o" in args


def test_build_patch_args_morphe_uses_long_flags(tmp_path: Path) -> None:
    p = _make_patcher(tmp_path, MORPHE_CLI)
    args = p._build_patch_args(
        stock_apk=tmp_path / "in.apk",
        output_apk=tmp_path / "out.apk",
        patches_jars=[tmp_path / "p.jar"],
        exclude_patches=[],
        include_patches=[],
        merge_jars=[],
        patches_post=[],
        force=False,
    )
    assert "--input" in args
    assert "--output" in args
    assert "--purge" in args
