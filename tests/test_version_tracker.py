"""Tests for scripts/version_tracker.py."""

# ruff: noqa: S101, TC003, TC002

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from scripts.version_tracker import (
    CheckResult,
    VersionDiff,
    detect_changes,
    execute_show_command,
    extract_current_versions,
    load_state,
    resolve_patches_tags,
    save_state,
)

# ---------------------------------------------------------------------------
# resolve_patches_tags
# ---------------------------------------------------------------------------


class TestResolvePatchesTags:
    def test_resolves_unique_enabled_sources(self) -> None:
        config: dict[str, object] = {
            "patches-source": "MorpheApp/morphe-patches",
            "patches-version": "latest",
            "A": {},
            "B": {"patches-source": ["MorpheApp/morphe-patches", "x/y"], "patches-version": "dev"},
            "Off": {"enabled": False, "patches-source": "never/resolved"},
            "C": {"patches-source": "brosssh/revanced-external-bundles"},
        }
        with patch(
            "scripts.version_tracker._resolve_github_release_asset",
            side_effect=lambda src, _ext, _fb, version: ("f.mpp", "url", f"{src}-{version}-tag"),
        ):
            tags = resolve_patches_tags(config)
        assert tags == {
            "patches_tag_MorpheApp/morphe-patches@latest": "MorpheApp/morphe-patches-latest-tag",
            "patches_tag_MorpheApp/morphe-patches@dev": "MorpheApp/morphe-patches-dev-tag",
            "patches_tag_x/y@dev": "x/y-dev-tag",
        }


# ---------------------------------------------------------------------------
# save_state / load_state
# ---------------------------------------------------------------------------


class TestSaveLoadState:
    def test_round_trip(self, tmp_path: Path) -> None:
        state_file = tmp_path / "versions.json"
        data = {"global_cli_version": "5.0.0", "global_patches_version": "4.0.0"}
        save_state(data, state_path=state_file)
        loaded = load_state(state_path=state_file)
        assert loaded["global_cli_version"] == "5.0.0"
        assert loaded["global_patches_version"] == "4.0.0"

    def test_load_returns_empty_when_missing(self, tmp_path: Path) -> None:
        missing = tmp_path / "nope.json"
        result = load_state(state_path=missing)
        assert result == {}

    def test_save_creates_parent_dirs(self, tmp_path: Path) -> None:
        deep = tmp_path / "a" / "b" / "versions.json"
        save_state({"key": "val"}, state_path=deep)
        assert deep.exists()

    def test_save_empty_dict(self, tmp_path: Path) -> None:
        state_file = tmp_path / "versions.json"
        save_state({}, state_path=state_file)
        loaded = load_state(state_path=state_file)
        assert loaded == {}


# ---------------------------------------------------------------------------
# detect_changes
# ---------------------------------------------------------------------------


class TestDetectChanges:
    def test_no_changes_returns_empty(self) -> None:
        current = {"global_cli_version": "5.0.0"}
        saved = {"global_cli_version": "5.0.0"}
        assert detect_changes(current, saved) == []

    def test_detects_version_change(self) -> None:
        current = {"global_cli_version": "6.0.0"}
        saved = {"global_cli_version": "5.0.0"}
        changes = detect_changes(current, saved)
        assert len(changes) == 1
        assert changes[0].key == "global_cli_version"
        assert changes[0].old == "5.0.0"
        assert changes[0].new == "6.0.0"
        assert changes[0].change_type == "modified"

    def test_detects_new_key(self) -> None:
        current = {"global_cli_version": "5.0.0", "new_key": "val"}
        saved = {"global_cli_version": "5.0.0"}
        changes = detect_changes(current, saved)
        assert any(c.key == "new_key" and c.change_type == "added" for c in changes)

    def test_detects_removed_key(self) -> None:
        current = {"global_cli_version": "5.0.0"}
        saved = {"global_cli_version": "5.0.0", "removed_key": "old"}
        changes = detect_changes(current, saved)
        assert any(c.key == "removed_key" and c.change_type == "removed" for c in changes)

    def test_multiple_changes(self) -> None:
        current = {"a": "2", "b": "2"}
        saved = {"a": "1", "b": "1"}
        changes = detect_changes(current, saved)
        assert len(changes) == 2


# ---------------------------------------------------------------------------
# extract_current_versions (operates on raw TOML dict)
# ---------------------------------------------------------------------------


class TestExtractCurrentVersions:
    def test_extracts_global_cli_version(self) -> None:
        config: dict[str, object] = {"cli-version": "5.0.0"}
        versions = extract_current_versions(config)
        assert versions["global_cli_version"] == "5.0.0"

    def test_extracts_global_patches_version(self) -> None:
        config: dict[str, object] = {"patches-version": "4.0.0"}
        versions = extract_current_versions(config)
        assert versions["global_patches_version"] == "4.0.0"

    def test_extracts_patches_source_string(self) -> None:
        config: dict[str, object] = {"patches-source": "owner/repo"}
        versions = extract_current_versions(config)
        assert versions["global_patches_source"] == "owner/repo"

    def test_extracts_patches_source_list(self) -> None:
        config: dict[str, object] = {"patches-source": ["owner/a", "owner/b"]}
        versions = extract_current_versions(config)
        assert "owner/a" in versions["global_patches_source"]
        assert "owner/b" in versions["global_patches_source"]

    def test_extracts_app_version(self) -> None:
        config: dict[str, object] = {
            "cli-version": "5.0.0",
            "YouTube": {"enabled": True, "version": "18.0.0"},
        }
        versions = extract_current_versions(config)
        assert versions.get("app_youtube_version") == "18.0.0"

    def test_skips_disabled_app(self) -> None:
        config: dict[str, object] = {
            "Twitter": {"enabled": False, "version": "9.0.0"},
        }
        versions = extract_current_versions(config)
        assert "app_twitter_version" not in versions

    def test_defaults_when_missing(self) -> None:
        versions = extract_current_versions({})
        assert versions["global_cli_version"] == "latest"
        assert versions["global_patches_version"] == "latest"


# ---------------------------------------------------------------------------
# CheckResult and VersionDiff dataclasses
# ---------------------------------------------------------------------------


class TestCheckResult:
    def test_needs_build_true_when_changes(self) -> None:
        change = VersionDiff(key="cli", old="1", new="2", change_type="modified")
        result = CheckResult(needs_build=True, changes=[change])
        assert result.needs_build is True
        assert len(result.changes) == 1

    def test_needs_build_false_no_changes(self) -> None:
        result = CheckResult(needs_build=False, changes=[])
        assert result.needs_build is False
        assert result.changes == []


class TestVersionDiff:
    def test_fields_accessible(self) -> None:
        diff = VersionDiff(key="comp", old="v1", new="v2", change_type="modified")
        assert diff.key == "comp"
        assert diff.old == "v1"
        assert diff.new == "v2"
        assert diff.change_type == "modified"


# ---------------------------------------------------------------------------
# load_config / check_needs_build on a JSON config
# ---------------------------------------------------------------------------


class TestJsonConfig:
    def _write(self, tmp_path: Path, name: str) -> str:
        import json

        config_path = tmp_path / name
        config_path.write_text(json.dumps({"cli-version": "5.0.0", "patches-source": "ReVanced/revanced-patches"}))
        return str(config_path)

    def test_load_config_reads_json(self, tmp_path: Path) -> None:
        from scripts.version_tracker import load_config

        config = load_config(self._write(tmp_path, "a.json"))

        assert extract_current_versions(config)["global_cli_version"] == "5.0.0"

    def test_check_needs_build_without_saved_state(self, tmp_path: Path) -> None:
        from scripts.version_tracker import check_needs_build

        result = check_needs_build(self._write(tmp_path, "b.json"), state_path=tmp_path / "missing.json")

        assert result == CheckResult(needs_build=True, changes=[])


# ---------------------------------------------------------------------------
# execute_show_command
# ---------------------------------------------------------------------------


class TestExecuteShowCommand:
    def test_execute_show_command_with_state(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        state_file = tmp_path / "state.json"
        save_state({"test_key": "test_value"}, state_path=state_file)

        result = execute_show_command(state_file)

        assert result == 0
        captured = capsys.readouterr()
        assert '"test_key": "test_value"' in captured.out

    def test_execute_show_command_empty(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        state_file = tmp_path / "empty.json"

        result = execute_show_command(state_file)

        assert result == 0
        captured = capsys.readouterr()
        assert captured.out.strip() == "{}"


# ---------------------------------------------------------------------------
# execute_check_command
# ---------------------------------------------------------------------------


class TestExecuteCheckCommand:
    @patch("scripts.version_tracker.check_needs_build")
    @patch("scripts.version_tracker.set_github_output")
    @patch("scripts.version_tracker.format_changes_for_github_output")
    def test_needs_build_true_with_changes(
        self,
        mock_format: MagicMock,
        mock_set_github: MagicMock,
        mock_check: MagicMock,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        change = VersionDiff(key="cli", old="1", new="2", change_type="modified")
        mock_check.return_value = CheckResult(needs_build=True, changes=[change])
        mock_format.return_value = "formatted_changes"

        from scripts.version_tracker import execute_check_command

        result = execute_check_command("config.toml", None)

        assert result == 0
        mock_check.assert_called_once_with("config.toml", None)
        mock_format.assert_called_once_with([change])

        assert mock_set_github.call_count == 2
        mock_set_github.assert_any_call("needs_build", "true")
        mock_set_github.assert_any_call("changes", "formatted_changes")

        captured = capsys.readouterr()
        assert captured.out.strip() == "true"

    @patch("scripts.version_tracker.check_needs_build")
    @patch("scripts.version_tracker.set_github_output")
    @patch("scripts.version_tracker.format_changes_for_github_output")
    def test_needs_build_false_no_changes(
        self,
        mock_format: MagicMock,
        mock_set_github: MagicMock,
        mock_check: MagicMock,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        mock_check.return_value = CheckResult(needs_build=False, changes=[])

        from scripts.version_tracker import execute_check_command

        result = execute_check_command("config.toml", None)

        assert result == 0
        mock_check.assert_called_once_with("config.toml", None)
        mock_format.assert_not_called()

        mock_set_github.assert_called_once_with("needs_build", "false")

        captured = capsys.readouterr()
        assert captured.out.strip() == "false"
