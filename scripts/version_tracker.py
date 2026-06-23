#!/usr/bin/env python3
"""Version tracker for smart rebuild detection."""

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


class AppVersionInfo(TypedDict, total=False):
    patches_source: str
    cli_source: str
    version: str


class StateDict(TypedDict, total=False):
    global_cli_version: str
    global_patches_version: str
    global_patches_source: str


class Command(Enum):
    CHECK = auto()
    SAVE = auto()
    SHOW = auto()
    RESET = auto()


@dataclass(frozen=True, slots=True)
class AppVersionState:
    patches_source: str
    cli_source: str
    version: str
    integrations_version: str | None = None


@dataclass(frozen=True, slots=True)
class BuildState:
    global_cli_version: str
    global_patches_version: str
    global_patches_source: str
    app_versions: dict[str, AppVersionState] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class VersionDiff:
    key: str
    old: str
    new: str
    change_type: str


@dataclass(frozen=True, slots=True)
class CheckResult:
    needs_build: bool
    changes: list[VersionDiff]


type VersionMap = dict[str, str]


@lru_cache(maxsize=1)
def load_state(state_path: Path | None = None) -> VersionMap:
    path = state_path or STATE_FILE
    if path.exists():
        try:
            content = path.read_bytes()
            return dict(orjson.loads(content))
        except (orjson.JSONDecodeError, OSError) as e:
            print(f"Warning: Could not read state file: {e}", file=sys.stderr)
    return {}


def save_state(versions: VersionMap, state_path: Path | None = None) -> None:
    path = state_path or STATE_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    json_bytes: bytes = orjson.dumps(versions, option=orjson.OPT_INDENT_2)
    path.write_bytes(json_bytes + b"\n")
    print(f"State saved to {path}", file=sys.stderr)


@lru_cache(maxsize=4)
def load_config(config_path: str) -> dict[str, object]:
    path = Path(config_path)
    try:
        with path.open("rb") as f:
            return dict(tomllib.load(f))
    except (OSError, tomllib.TOMLDecodeError) as e:
        print(f"Error reading config: {e}", file=sys.stderr)
        sys.exit(1)


def _normalize_patches_source(value: object) -> str | None:
    match value:
        case str(s):
            return s
        case list():
            return ",".join(str(s) for s in value)
        case _:
            return None


def extract_current_versions(config: dict[str, object]) -> VersionMap:
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
        if not isinstance(value, dict) or not value.get("enabled", True):
            continue

        app_prefix = f"app_{key.lower().replace(' ', '-')}_"

        if patches_normalized := _normalize_patches_source(value.get("patches-source", global_patches_src)):
            versions[app_prefix + "patches_source"] = patches_normalized

        if cli_src := value.get("cli-source"):
            versions[app_prefix + "cli_source"] = str(cli_src)

        versions[app_prefix + "version"] = str(value.get("version", "auto"))

        if integrations_ver := value.get("integrations-version"):
            versions[app_prefix + "integrations_version"] = str(integrations_ver)

    return versions


def extract_build_state(config: dict[str, object]) -> BuildState:
    global_cli_ver = str(config.get("cli-version", "latest"))
    global_patches_ver = str(config.get("patches-version", "latest"))
    global_patches_src = config.get("patches-source", "")
    normalized_global_patches = _normalize_patches_source(global_patches_src) or ""
    app_versions: dict[str, AppVersionState] = {}
    for key, value in config.items():
        if type(value) is not dict or not value.get("enabled", True):
            continue

        app_key = key.lower().replace(" ", "-")

        patches_normalized = _normalize_patches_source(value.get("patches-source", global_patches_src)) or ""
        app_versions[app_key] = AppVersionState(
            patches_source=patches_normalized,
            cli_source=str(value["cli-source"]) if "cli-source" in value else "",
            version=str(value.get("version", "auto")),
            integrations_version=str(value["integrations-version"]) if "integrations-version" in value else None,
        )
    return BuildState(
        global_cli_version=global_cli_ver,
        global_patches_version=global_patches_ver,
        global_patches_source=normalized_global_patches,
        app_versions=app_versions,
    )


def detect_changes(current: VersionMap, saved: VersionMap) -> list[VersionDiff]:
    changes: list[VersionDiff] = []
    for key, cur_val in current.items():
        saved_val = saved.get(key)
        if saved_val is None:
            changes.append(VersionDiff(key, "", cur_val, "added"))
        elif cur_val != saved_val:
            changes.append(VersionDiff(key, saved_val, cur_val, "modified"))
    changes.extend(VersionDiff(key, saved[key], "", "removed") for key in saved if key not in current)
    return changes


def check_needs_build(config_path: str, state_path: Path | None = None) -> CheckResult:
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
    gh_output = os.environ.get("GITHUB_OUTPUT")
    if gh_output:
        with Path(gh_output).open("a", encoding="utf-8") as f:
            f.write(f"{key}={value}\n")
    print(f"  {key}={value}", file=sys.stderr)


def format_changes_for_github_output(changes: list[VersionDiff]) -> str:
    return "\n".join(
        f"::notice title={change.key}::{change.change_type}: {change.old} -> {change.new}" for change in changes
    )


def execute_check_command(config_path: str, state_path: Path | None) -> int:
    result = check_needs_build(config_path, state_path)
    set_github_output("needs_build", str(result.needs_build).lower())
    if result.changes:
        github_output = format_changes_for_github_output(result.changes)
        set_github_output("changes", github_output)
    print("true" if result.needs_build else "false")
    return 0


def execute_save_command(config_path: str, state_path: Path | None) -> int:
    config = load_config(config_path)
    current = extract_current_versions(config)
    save_state(current, state_path)
    return 0


def execute_show_command(state_path: Path | None) -> int:
    state = load_state(state_path)
    if state:
        print(orjson.dumps(state, option=orjson.OPT_INDENT_2).decode("utf-8"))
    else:
        print("{}")
    return 0


def execute_reset_command(state_path: Path | None) -> int:
    save_state({}, state_path)
    print("State reset")
    return 0


def determine_command(args: argparse.Namespace) -> Command:
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
    parser = argparse.ArgumentParser(description="Track build versions for smart rebuild detection")
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
