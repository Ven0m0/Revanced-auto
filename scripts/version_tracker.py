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

import argparse
import json
import os
import sys
import tomllib
from pathlib import Path

STATE_FILE = Path(".github/last_built_versions.json")


def load_state(state_path: Path | None = None) -> dict[str, str]:
    """Load the persisted build state from the JSON file.

    Args:
        state_path: Path to the state file. Defaults to STATE_FILE.

    Returns:
        Dictionary of component -> version mappings.
    """
    path = state_path or STATE_FILE
    if path.exists():
        try:
            return dict(json.loads(path.read_text(encoding="utf-8")))
        except (json.JSONDecodeError, OSError) as e:
            print(f"Warning: Could not read state file: {e}", file=sys.stderr)
    return {}


def save_state(versions: dict[str, str], state_path: Path | None = None) -> None:
    """Save current build state to the JSON file.

    Args:
        versions: Dictionary of component -> version mappings.
        state_path: Path to the state file. Defaults to STATE_FILE.
    """
    path = state_path or STATE_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(versions, indent=2) + "\n", encoding="utf-8")
    print(f"State saved to {path}", file=sys.stderr)


def load_config(config_path: str) -> dict[str, object]:
    """Load and parse a TOML config file.

    Args:
        config_path: Path to config.toml.

    Returns:
        Parsed TOML as a dictionary.

    Raises:
        SystemExit: If the file cannot be read or parsed.
    """
    try:
        with Path(config_path).open("rb") as f:
            return dict(tomllib.load(f))
    except (OSError, tomllib.TOMLDecodeError) as e:
        print(f"Error reading config: {e}", file=sys.stderr)
        sys.exit(1)


def extract_current_versions(config: dict[str, object]) -> dict[str, str]:
    """Extract version identifiers from config for comparison.

    Tracks:
    - Global cli-version and patches-version
    - Per-app: patches-source, cli-source, version, enabled status

    Args:
        config: Parsed TOML configuration.

    Returns:
        Flat dictionary of trackable version keys.
    """
    versions: dict[str, str] = {}

    global_cli_ver = str(config.get("cli-version", "latest"))
    global_patches_ver = str(config.get("patches-version", "latest"))
    global_patches_src = config.get("patches-source", "")

    versions["global_cli_version"] = global_cli_ver
    versions["global_patches_version"] = global_patches_ver
    if global_patches_src:
        if isinstance(global_patches_src, list):
            versions["global_patches_source"] = ",".join(str(s) for s in global_patches_src)
        else:
            versions["global_patches_source"] = str(global_patches_src)

    for key, value in config.items():
        if not isinstance(value, dict):
            continue

        enabled = value.get("enabled", True)
        if not enabled:
            continue

        app_key = key.lower().replace(" ", "-")

        patches_src = value.get("patches-source", global_patches_src)
        if isinstance(patches_src, list):
            versions[f"app_{app_key}_patches_source"] = ",".join(str(s) for s in patches_src)
        elif patches_src:
            versions[f"app_{app_key}_patches_source"] = str(patches_src)

        cli_src = value.get("cli-source", "")
        if cli_src:
            versions[f"app_{app_key}_cli_source"] = str(cli_src)

        app_ver = value.get("version", "auto")
        versions[f"app_{app_key}_version"] = str(app_ver)

    return versions


def check_needs_build(
    config_path: str,
    state_path: Path | None = None,
) -> bool:
    """Compare current config against saved state to detect changes.

    Args:
        config_path: Path to config.toml.
        state_path: Path to the state file.

    Returns:
        True if a rebuild is needed.
    """
    config = load_config(config_path)
    current = extract_current_versions(config)
    saved = load_state(state_path)

    if not saved:
        print("No previous build state found — build needed", file=sys.stderr)
        return True

    changes: list[str] = []
    for key, cur_val in current.items():
        saved_val = saved.get(key, "")
        if cur_val != saved_val:
            changes.append(f"  {key}: {saved_val!r} -> {cur_val!r}")

    changes.extend(f"  {key}: removed" for key in saved if key not in current)

    if changes:
        print("Changes detected:", file=sys.stderr)
        for change in changes:
            print(change, file=sys.stderr)
        return True

    print("No changes detected", file=sys.stderr)
    return False


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


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Track build versions for smart rebuild detection",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    check_parser = subparsers.add_parser("check", help="Check if build is needed")
    check_parser.add_argument("--config", required=True, help="Path to config.toml")
    check_parser.add_argument(
        "--state-file", help="Path to state file (default: .github/last_built_versions.json)"
    )

    save_parser = subparsers.add_parser("save", help="Save current state after successful build")
    save_parser.add_argument("--config", required=True, help="Path to config.toml")
    save_parser.add_argument("--state-file", help="Path to state file")

    subparsers.add_parser("show", help="Show current state")

    subparsers.add_parser("reset", help="Reset state file")

    args = parser.parse_args()
    state_path = Path(args.state_file) if hasattr(args, "state_file") and args.state_file else None

    if args.command == "check":
        needs_build = check_needs_build(args.config, state_path)
        set_github_output("needs_build", str(needs_build).lower())
        print("true" if needs_build else "false")
        sys.exit(0)

    if args.command == "save":
        config = load_config(args.config)
        current = extract_current_versions(config)
        save_state(current, state_path)
        sys.exit(0)

    if args.command == "show":
        state = load_state(state_path)
        if state:
            print(json.dumps(state, indent=2))
        else:
            print("{}")
        sys.exit(0)

    if args.command == "reset":
        save_state({}, state_path)
        print("State reset")
        sys.exit(0)

    sys.exit(1)


if __name__ == "__main__":
    main()
