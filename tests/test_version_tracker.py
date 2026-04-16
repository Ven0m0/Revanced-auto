"""Tests for scripts/version_tracker.py and scripts/lib/version_tracker.py."""

# ruff: noqa: S101, PLC0415, TC003

from __future__ import annotations

from pathlib import Path

from scripts.version_tracker import (
    CheckResult,
    VersionDiff,
    detect_changes,
    extract_current_versions,
    load_state,
    save_state,
)

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
        config: dict = {"cli-version": "5.0.0"}
        versions = extract_current_versions(config)
        assert versions["global_cli_version"] == "5.0.0"

    def test_extracts_global_patches_version(self) -> None:
        config: dict = {"patches-version": "4.0.0"}
        versions = extract_current_versions(config)
        assert versions["global_patches_version"] == "4.0.0"

    def test_extracts_patches_source_string(self) -> None:
        config: dict = {"patches-source": "owner/repo"}
        versions = extract_current_versions(config)
        assert versions["global_patches_source"] == "owner/repo"

    def test_extracts_patches_source_list(self) -> None:
        config: dict = {"patches-source": ["owner/a", "owner/b"]}
        versions = extract_current_versions(config)
        assert "owner/a" in versions["global_patches_source"]
        assert "owner/b" in versions["global_patches_source"]

    def test_extracts_app_version(self) -> None:
        config: dict = {
            "cli-version": "5.0.0",
            "YouTube": {"enabled": True, "version": "18.0.0"},
        }
        versions = extract_current_versions(config)
        assert versions.get("app_youtube_version") == "18.0.0"

    def test_skips_disabled_app(self) -> None:
        config: dict = {
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
# VersionTracker wrapper (scripts/lib/version_tracker.py)
# Uses raw TOML dict as config since extract_current_versions expects a dict
# ---------------------------------------------------------------------------


class TestVersionTrackerWrapper:
    def _make_config_dict(
        self,
        patches_version: str = "4.0.0",
        cli_version: str = "5.0.0",
        patches_source: str = "ReVanced/revanced-patches",
    ) -> dict:
        """Build a minimal TOML-like config dict for the version tracker."""
        return {
            "patches-version": patches_version,
            "cli-version": cli_version,
            "patches-source": patches_source,
        }

    def test_check_returns_true_when_no_saved_state(self, tmp_path: Path) -> None:
        from scripts.lib.version_tracker import VersionTracker

        config = self._make_config_dict()
        state_file = tmp_path / "versions.json"
        # Don't create the state file — no prior state means build needed
        tracker = VersionTracker(config)

        # Patch STATE_FILE via the underlying module so load_state sees no file
        import scripts.version_tracker as vt_mod

        original = vt_mod.STATE_FILE
        vt_mod.STATE_FILE = state_file  # type: ignore[misc]
        try:
            needs = tracker.check()
        finally:
            vt_mod.STATE_FILE = original  # type: ignore[misc]

        assert needs is True

    def test_get_state_returns_dict(self, tmp_path: Path) -> None:
        from scripts.lib.version_tracker import VersionTracker

        state_file = tmp_path / "versions.json"
        save_state({"global_cli_version": "5.0.0"}, state_path=state_file)

        import scripts.version_tracker as vt_mod

        original = vt_mod.STATE_FILE
        vt_mod.STATE_FILE = state_file  # type: ignore[misc]
        vt_mod.load_state.cache_clear()  # clear lru_cache so patched path is used
        try:
            config = self._make_config_dict(cli_version="5.0.0")
            tracker = VersionTracker(config)
            state = tracker.get_state()
        finally:
            vt_mod.STATE_FILE = original  # type: ignore[misc]
            vt_mod.load_state.cache_clear()

        assert state.get("global_cli_version") == "5.0.0"
