"""Tests for the patcher module."""

# ruff: noqa: S101
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from scripts.builder.cli_profiles import CLIProfile
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
