#!/usr/bin/env python3
"""Version tracker for smart rebuild detection.

Tracks last successfully built versions of ReVanced CLI, patches, and apps.
Compares current state against persisted state to determine if a rebuild is needed.

Inspired by X-Abhishek-X/ReVanced-Automated-Build-Scripts check_updates.py.

Usage:
    # Check if build is needed (reads config.toml, compares with state file)
    python3 version_tracker.py check --config config.toml

    # Save current build state after successful build
    python3 version_tracker.py save --config config.toml

    # Show current state
    python3 version_tracker.py show

    # Reset state file
    python3 version_tracker.py reset
"""

from __future__ import annotations

import argparse
import os
import sys
import tomllib
from dataclasses import dataclass, field
from enum import Enum, auto
from functools import lru_cache
from pathlib import Path
from typing import Final, TypedDict

import orjson

STATE_FILE: Final[Path] = Path(".github/last_built_versions.json")


class VersionState(TypedDict):
    """State dictionary for version tracking."""

    component: str
    version: str


class AppVersionInfo(TypedDict, total=False):
    """App version information from config."""

    patches_source: str
    cli_source: str
    version: str


class StateDict(TypedDict, total=False):
    """State file structure."""

    global_cli_version: str
    global_patches_version: str
    global_patches_source: str


class Command(Enum):
    """Available CLI commands."""

    CHECK = auto()
    SAVE = auto()
    SHOW = auto()
    RESET = auto()


@dataclass(frozen=True, slots=True)
class AppVersionState:
    """Per-app version tracking state.

    Attributes:
        patches_source: Source repository for patches.
        cli_source: Source repository for CLI.
        version: App version.
        integrations_version: Optional integrations version.

    """

    patches_source: str
    cli_source: str
    version: str
    integrations_version: str | None = None


@dataclass(frozen=True, slots=True)
class BuildState:
    """Tracks version state for smart rebuild detection.

    Attributes:
        global_cli_version: Global CLI version.
        global_patches_version: Global patches version.
        global_patches_source: Global patches source repository.
        app_versions: Per-app version tracking dictionary.

    """

    global_cli_version: str
    global_patches_version: str
    global_patches_source: str
    app_versions: dict[str, AppVersionState] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class VersionDiff:
    """Represents a version difference.

    Attributes:
        key: Component key.
        old: Old version value.
        new: New version value.
        change_type: Type of change.

    """

    key: str
    old: str
    new: str
    change_type: str


@dataclass(frozen=True, slots=True)
class CheckResult:
    """Result of a build check operation.

    Attributes:
        needs_build: Whether a rebuild is needed.
        changes: List of version changes detected.

    """

    needs_build: bool
    changes: list[VersionDiff]


type VersionMap = dict[str, str]


@lru_cache(maxsize=1)
def load_state(state_path: Path | None = None) -> VersionMap:
    """Load the persisted build state from the JSON file.

    Args:
        state_path: Path to the state file. Defaults to STATE_FILE.

    Returns:
        Dictionary of component -> version mappings.

    """
    path = state_path or STATE_FILE
    if path.exists():
        try:
            content = path.read_bytes()
            return dict(orjson.loads(content))
        except (orjson.JSONDecodeError, OSError) as e:
            print(f"Warning: Could not read state file: {e}", file=sys.stderr)
    return {}


def save_state(versions: VersionMap, state_path: Path | None = None) -> None:
    """Save current build state to the JSON file.

    Args:
        versions: Dictionary of component -> version mappings.
        state_path: Path to the state file. Defaults to STATE_FILE.

    """
    path = state_path or STATE_FILE
    path.parent.mkdir(parents=True, exist_ok=True)

    json_bytes: bytes = orjson.dumps(versions, option=orjson.OPT_INDENT_2)
    path.write_bytes(json_bytes + b"\n")
    print(f"State saved to {path}", file=sys.stderr)


@lru_cache(maxsize=4)
def load_config(config_path: str) -> dict[str, object]:
    """Load and parse a TOML config file.

    Args:
        config_path: Path to config.toml.

    Returns:
        Parsed TOML as a dictionary.

    Raises:
        SystemExit: If the file cannot be read or parsed.

    """
    path = Path(config_path)
    try:
        with path.open("rb") as f:
            return dict(tomllib.load(f))
    except (OSError, tomllib.TOMLDecodeError) as e:
        print(f"Error reading config: {e}", file=sys.stderr)
        sys.exit(1)


def _normalize_patches_source(value: object) -> str | None:
    """Normalize patches source to string.

    Args:
        value: Raw patches source (str or list).

    Returns:
        Normalized string or None.

    """
    match value:
        case str(s):
            return s
        case list():
            return ",".join(str(s) for s in value)
        case _:
            return None


def extract_current_versions(config: dict[str, object]) -> VersionMap:
    """Extract version identifiers from config for comparison.

    Tracks:
    - Global cli-version and patches-version
    - Per-app: patches-source, cli-source, version, integrations, enabled status

    Args:
        config: Parsed TOML configuration.

    Returns:
        Flat dictionary of trackable version keys.

    """
    versions: VersionMap = {}

    global_cli_ver = str(config.get("cli-version", "latest"))
    global_patches_ver = str(config.get("patches-version", "latest"))
    global_patches_src = config.get("patches-source", "")

    versions["global_cli_version"] = global_cli_ver
    versions["global_patches_version"] = global_patches_ver

    normalized = _normalize_patches_source(global_patches_src)
    if normalized:
        versions["global_patches_source"] = normalized

    for key, value in config.items():
        if not isinstance(value, dict):
            continue

        enabled = value.get("enabled", True)
        if not enabled:
            continue

        app_key = key.lower().replace(" ", "-")

        patches_src = value.get("patches-source", global_patches_src)
        patches_normalized = _normalize_patches_source(patches_src)
        if patches_normalized:
            versions[f"app_{app_key}_patches_source"] = patches_normalized

        cli_src = value.get("cli-source", "")
        if cli_src:
            versions[f"app_{app_key}_cli_source"] = str(cli_src)

        app_ver = value.get("version", "auto")
        versions[f"app_{app_key}_version"] = str(app_ver)

        integrations_ver = value.get("integrations-version")
        if integrations_ver:
            versions[f"app_{app_key}_integrations_version"] = str(integrations_ver)

    return versions


def extract_build_state(config: dict[str, object]) -> BuildState:
    """Extract build state from config in structured format.

    Args:
        config: Parsed TOML configuration.

    Returns:
        BuildState with global and per-app version tracking.

    """
    global_cli_ver = str(config.get("cli-version", "latest"))
    global_patches_ver = str(config.get("patches-version", "latest"))
    global_patches_src = config.get("patches-source", "")
    normalized_global_patches = _normalize_patches_source(global_patches_src) or ""

    app_versions: dict[str, AppVersionState] = {}

    for key, value in config.items():
        if not isinstance(value, dict):
            continue

        enabled = value.get("enabled", True)
        if not enabled:
            continue

        app_key = key.lower().replace(" ", "-")

        patches_src = value.get("patches-source", global_patches_src)
        patches_normalized = _normalize_patches_source(patches_src) or ""

        cli_src = value.get("cli-source", "")

        app_ver = value.get("version", "auto")

        integrations_ver = value.get("integrations-version")

        app_versions[app_key] = AppVersionState(
            patches_source=patches_normalized,
            cli_source=str(cli_src) if cli_src else "",
            version=str(app_ver),
            integrations_version=str(integrations_ver) if integrations_ver else None,
        )

    return BuildState(
        global_cli_version=global_cli_ver,
        global_patches_version=global_patches_ver,
        global_patches_source=normalized_global_patches,
        app_versions=app_versions,
    )


def detect_changes(current: VersionMap, saved: VersionMap) -> list[VersionDiff]:
    """Detect version changes between current and saved state.

    Args:
        current: Current version state.
        saved: Saved version state.

    Returns:
        List of version differences.

    """
    changes: list[VersionDiff] = []

    for key, cur_val in current.items():
        saved_val = saved.get(key)
        if saved_val is None:
            changes.append(VersionDiff(key, "", cur_val, "added"))
        elif cur_val != saved_val:
            changes.append(VersionDiff(key, saved_val, cur_val, "modified"))

    changes.extend(VersionDiff(key, saved[key], "", "removed") for key in saved if key not in current)

    return changes


def check_needs_build(
    config_path: str,
    state_path: Path | None = None,
) -> CheckResult:
    """Compare current config against saved state to detect changes.

    Args:
        config_path: Path to config.toml.
        state_path: Path to the state file.

    Returns:
        CheckResult with needs_build flag and list of changes.

    """
    config = load_config(config_path)
    current = extract_current_versions(config)
    saved = load_state(state_path)

    if not saved:
        print("No previous build state found — build needed", file=sys.stderr)
        return CheckResult(needs_build=True, changes=[])

    changes = detect_changes(current, saved)

    if changes:
        print("Changes detected:", file=sys.stderr)
        for change in changes:
            match change.change_type:
                case "modified":
                    print(f"  {change.key}: {change.old!r} -> {change.new!r}", file=sys.stderr)
                case "added":
                    print(f"  {change.key}: added -> {change.new!r}", file=sys.stderr)
                case "removed":
                    print(f"  {change.key}: {change.old!r} -> removed", file=sys.stderr)

    else:
        print("No changes detected", file=sys.stderr)

    return CheckResult(needs_build=bool(changes), changes=changes)


def set_github_output(key: str, value: str) -> None:
    """Write key=value to GITHUB_OUTPUT if available.

    Args:
        key: Output key name.
        value: Output value.

    """
    gh_output = os.environ.get("GITHUB_OUTPUT")
    if gh_output:
        with Path(gh_output).open("a", encoding="utf-8") as f:
            f.write(f"{key}={value}\n")
    print(f"  {key}={value}", file=sys.stderr)


def format_changes_for_github_output(changes: list[VersionDiff]) -> str:
    """Format changes list for GitHub Actions workflow command.

    Args:
        changes: List of version differences.

    Returns:
        Formatted string for workflow commands.

    """
    return "\n".join(
        f"::notice title={change.key}::{change.change_type}: {change.old} -> {change.new}"
        for change in changes
    )


def execute_check_command(config_path: str, state_path: Path | None) -> int:
    """Execute the check command.

    Args:
        config_path: Path to config.toml.
        state_path: Optional path to state file.

    Returns:
        Exit code.

    """
    result = check_needs_build(config_path, state_path)
    set_github_output("needs_build", str(result.needs_build).lower())

    if result.changes:
        github_output = format_changes_for_github_output(result.changes)
        set_github_output("changes", github_output)

    print("true" if result.needs_build else "false")
    return 0


def execute_save_command(config_path: str, state_path: Path | None) -> int:
    """Execute the save command.

    Args:
        config_path: Path to config.toml.
        state_path: Optional path to state file.

    Returns:
        Exit code.

    """
    config = load_config(config_path)
    current = extract_current_versions(config)
    save_state(current, state_path)
    return 0


def execute_show_command(state_path: Path | None) -> int:
    """Execute the show command.

    Args:
        state_path: Optional path to state file.

    Returns:
        Exit code.

    """
    state = load_state(state_path)
    if state:
        print(orjson.dumps(state, option=orjson.OPT_INDENT_2).decode("utf-8"))
    else:
        print("{}")
    return 0


def execute_reset_command(state_path: Path | None) -> int:
    """Execute the reset command.

    Args:
        state_path: Optional path to state file.

    Returns:
        Exit code.

    """
    save_state({}, state_path)
    print("State reset")
    return 0


def determine_command(args: argparse.Namespace) -> Command:
    """Determine command from CLI arguments.

    Args:
        args: Parsed CLI arguments.

    Returns:
        Command to execute.

    """
    match args.command:
        case "check":
            return Command.CHECK
        case "save":
            return Command.SAVE
        case "show":
            return Command.SHOW
        case "reset":
            return Command.RESET
        case _:
            msg = f"unknown command: {args.command}"
            raise ValueError(msg)


def main() -> int:
    """CLI entry point.

    Returns:
        Exit code: 0 on success, 1 on error.

    """
    parser = argparse.ArgumentParser(
        description="Track build versions for smart rebuild detection",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    check_parser = subparsers.add_parser("check", help="Check if build is needed")
    check_parser.add_argument("--config", required=True, help="Path to config.toml")
    check_parser.add_argument("--state-file", help="Path to state file (default: .github/last_built_versions.json)")

    save_parser = subparsers.add_parser("save", help="Save current state after successful build")
    save_parser.add_argument("--config", required=True, help="Path to config.toml")
    save_parser.add_argument("--state-file", help="Path to state file")

    subparsers.add_parser("show", help="Show current state")

    subparsers.add_parser("reset", help="Reset state file")

    args = parser.parse_args()

    state_path: Path | None = Path(args.state_file) if hasattr(args, "state_file") and args.state_file else None

    command = determine_command(args)

    try:
        match command:
            case Command.CHECK:
                return execute_check_command(args.config, state_path)
            case Command.SAVE:
                return execute_save_command(args.config, state_path)
            case Command.SHOW:
                return execute_show_command(state_path)
            case Command.RESET:
                return execute_reset_command(state_path)
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    sys.exit(main())
