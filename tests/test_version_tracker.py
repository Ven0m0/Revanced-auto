"""Test suite for version tracker."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest

if TYPE_CHECKING:
    from pathlib import Path

from scripts.version_tracker import (
    CheckResult,
    Command,
    VersionDiff,
    check_needs_build,
    detect_changes,
    extract_current_versions,
    load_config,
    load_state,
    save_state,
    set_github_output,
)

if TYPE_CHECKING:
    from _pytest.monkeypatch import MonkeyPatch


class TestVersionDiff:
    """Tests for VersionDiff dataclass."""

    def test_version_diff_creation(self) -> None:
        """Test creating VersionDiff."""
        diff = VersionDiff(
            key="global_cli_version",
            old="5.0.0",
            new="5.1.0",
            change_type="modified",
        )
        assert diff.key == "global_cli_version"
        assert diff.old == "5.0.0"
        assert diff.new == "5.1.0"
        assert diff.change_type == "modified"


class TestCheckResult:
    """Tests for CheckResult dataclass."""

    def test_needs_build_true(self) -> None:
        """Test CheckResult with needs_build True."""
        changes = [VersionDiff("key", "old", "new", "modified")]
        result = CheckResult(needs_build=True, changes=changes)
        assert result.needs_build is True
        assert len(result.changes) == 1

    def test_needs_build_false(self) -> None:
        """Test CheckResult with needs_build False."""
        result = CheckResult(needs_build=False, changes=[])
        assert result.needs_build is False
        assert len(result.changes) == 0


class TestLoadState:
    """Tests for load_state function."""

    def test_load_existing_state(self, tmp_path: Path) -> None:
        """Test loading existing state file."""
        state_file = tmp_path / "state.json"
        state_file.write_text('{"global_cli_version": "5.0.0"}')

        # Clear cache first
        load_state.cache_clear()
        result = load_state(state_file)

        assert result["global_cli_version"] == "5.0.0"

    def test_load_nonexistent_state_returns_empty(self, tmp_path: Path) -> None:
        """Test loading non-existent state returns empty dict."""
        nonexistent = tmp_path / "nonexistent.json"

        load_state.cache_clear()
        result = load_state(nonexistent)

        assert result == {}

    def test_load_invalid_json_returns_empty(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        """Test loading invalid JSON returns empty dict with warning."""
        state_file = tmp_path / "state.json"
        state_file.write_text("not valid json")

        load_state.cache_clear()
        result = load_state(state_file)

        assert result == {}
        captured = capsys.readouterr()
        assert "Warning" in captured.err


class TestSaveState:
    """Tests for save_state function."""

    def test_save_state_creates_file(self, tmp_path: Path) -> None:
        """Test saving state creates file."""
        state_file = tmp_path / "state.json"
        versions = {"global_cli_version": "5.0.0"}

        save_state(versions, state_file)

        assert state_file.exists()
        content = state_file.read_text()
        assert "5.0.0" in content

    def test_save_state_creates_parent_dirs(self, tmp_path: Path) -> None:
        """Test saving state creates parent directories."""
        state_file = tmp_path / "subdir" / "state.json"
        versions = {"key": "value"}

        save_state(versions, state_file)

        assert state_file.exists()


class TestLoadConfig:
    """Tests for load_config function."""

    def test_load_valid_config(self, tmp_path: Path) -> None:
        """Test loading valid TOML config."""
        config_file = tmp_path / "config.toml"
        config_file.write_text('[app]\nname = "Test"')

        # Clear cache
        load_config.cache_clear()
        result = load_config(str(config_file))

        assert result["app"]["name"] == "Test"

    def test_load_invalid_config_exits(self, tmp_path: Path) -> None:
        """Test loading invalid config exits."""
        config_file = tmp_path / "config.toml"
        config_file.write_text("not valid toml {{{")

        load_config.cache_clear()
        with pytest.raises(SystemExit) as exc_info:
            load_config(str(config_file))
        assert exc_info.value.code == 1


class TestExtractCurrentVersions:
    """Tests for extract_current_versions function."""

    def test_extracts_global_versions(self) -> None:
        """Test extracting global version settings."""
        config: dict[str, object] = {
            "cli-version": "5.0.0",
            "patches-version": "4.0.0",
        }
        result = extract_current_versions(config)

        assert result["global_cli_version"] == "5.0.0"
        assert result["global_patches_version"] == "4.0.0"

    def test_extracts_patches_source_string(self) -> None:
        """Test extracting patches source as string."""
        config: dict[str, object] = {
            "patches-source": "ReVanced/revanced-patches",
        }
        result = extract_current_versions(config)

        assert result["global_patches_source"] == "ReVanced/revanced-patches"

    def test_extracts_patches_source_list(self) -> None:
        """Test extracting patches source as list."""
        config: dict[str, object] = {
            "patches-source": ["repo1", "repo2"],
        }
        result = extract_current_versions(config)

        assert result["global_patches_source"] == "repo1,repo2"

    def test_extracts_app_versions(self) -> None:
        """Test extracting per-app versions."""
        config: dict[str, object] = {
            "YouTube": {
                "enabled": True,
                "version": "19.16.39",
                "patches-source": "ReVanced/revanced-patches",
            },
        }
        result = extract_current_versions(config)

        assert result["app_youtube_version"] == "19.16.39"
        assert result["app_youtube_patches_source"] == "ReVanced/revanced-patches"

    def test_skips_disabled_apps(self) -> None:
        """Test that disabled apps are skipped."""
        config: dict[str, object] = {
            "YouTube": {
                "enabled": False,
                "version": "19.16.39",
            },
        }
        result = extract_current_versions(config)

        assert "app_youtube_version" not in result

    def test_normalizes_app_names(self) -> None:
        """Test that app names are normalized."""
        config: dict[str, object] = {
            "YouTube Music": {
                "enabled": True,
                "version": "auto",
            },
        }
        result = extract_current_versions(config)

        assert "app_youtube-music_version" in result


class TestDetectChanges:
    """Tests for detect_changes function."""

    def test_no_changes(self) -> None:
        """Test no changes detected."""
        current = {"key": "value"}
        saved = {"key": "value"}
        changes = detect_changes(current, saved)

        assert len(changes) == 0

    def test_modified_change(self) -> None:
        """Test detecting modified value."""
        current = {"key": "new"}
        saved = {"key": "old"}
        changes = detect_changes(current, saved)

        assert len(changes) == 1
        assert changes[0].change_type == "modified"
        assert changes[0].old == "old"
        assert changes[0].new == "new"

    def test_added_change(self) -> None:
        """Test detecting added key."""
        current = {"new_key": "value"}
        saved = {}
        changes = detect_changes(current, saved)

        assert len(changes) == 1
        assert changes[0].change_type == "added"
        assert changes[0].key == "new_key"

    def test_removed_change(self) -> None:
        """Test detecting removed key."""
        current = {}
        saved = {"old_key": "value"}
        changes = detect_changes(current, saved)

        assert len(changes) == 1
        assert changes[0].change_type == "removed"
        assert changes[0].key == "old_key"


class TestCheckNeedsBuild:
    """Tests for check_needs_build function."""

    def test_no_saved_state_needs_build(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        """Test that missing state triggers build."""
        config_file = tmp_path / "config.toml"
        config_file.write_text('[app]\nname = "Test"\nversion = "1.0"')
        state_file = tmp_path / "state.json"

        load_config.cache_clear()
        load_state.cache_clear()
        result = check_needs_build(str(config_file), state_file)

        assert result.needs_build is True
        captured = capsys.readouterr()
        assert "No previous build state" in captured.err

    def test_same_state_no_build_needed(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        """Test that identical state doesn't trigger build."""
        config_file = tmp_path / "config.toml"
        config_file.write_text('[test]\nname = "Test"\nversion = "1.0"')
        state_file = tmp_path / "state.json"
        state_file.write_text(
            '{"global_cli_version": "latest", "global_patches_version": "latest", "app_test_version": "1.0"}'
        )

        load_config.cache_clear()
        load_state.cache_clear()
        result = check_needs_build(str(config_file), state_file)

        assert result.needs_build is False
        captured = capsys.readouterr()
        assert "No changes detected" in captured.err


class TestSetGithubOutput:
    """Tests for set_github_output function."""

    def test_writes_to_github_output(self, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
        """Test writing to GITHUB_OUTPUT file."""
        output_file = tmp_path / "github_output"
        monkeypatch.setenv("GITHUB_OUTPUT", str(output_file))

        set_github_output("needs_build", "true")

        content = output_file.read_text()
        assert "needs_build=true" in content

    def test_prints_to_stderr_when_no_env(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Test printing to stderr when GITHUB_OUTPUT not set."""
        # Ensure GITHUB_OUTPUT is not set
        with patch.dict(os.environ, {}, clear=True):
            set_github_output("key", "value")

        captured = capsys.readouterr()
        assert "key=value" in captured.err


class TestCommand:
    """Tests for Command enum."""

    def test_command_values(self) -> None:
        """Test Command enum values."""
        assert Command.CHECK.name == "CHECK"
        assert Command.SAVE.name == "SAVE"
        assert Command.SHOW.name == "SHOW"
        assert Command.RESET.name == "RESET"


@pytest.mark.parametrize(
    ("current", "saved", "expected_changes"),
    [
        ({"k": "v"}, {"k": "v"}, 0),
        ({"k": "v2"}, {"k": "v1"}, 1),
        ({"k": "v"}, {}, 1),
        ({}, {"k": "v"}, 1),
    ],
)
def test_detect_changes_parametrized(
    current: dict[str, str],
    saved: dict[str, str],
    expected_changes: int,
) -> None:
    """Test change detection with various inputs."""
    changes = detect_changes(current, saved)
    assert len(changes) == expected_changes
