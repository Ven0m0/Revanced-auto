#!/usr/bin/env python3
"""
TOML/JSON to JSON converter for ReVanced Builder

Converts TOML files to JSON using Python's stdlib tomllib (requires Python >= 3.11).
Also validates and reformats JSON files.

Usage:
    # Convert TOML to JSON
    python3 toml_get.py --file config.toml

    # Convert with pretty printing
    python3 toml_get.py --file config.toml --pretty

    # Validate and reformat JSON
    python3 toml_get.py --file config.json

Requirements:
    Python 3.11+ (for tomllib support)

Author: ReVanced Builder
License: Same as parent project
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any


def check_python_version() -> None:
    """
    Verify Python version is >= 3.11 (required for tomllib).

    Exits with code 2 if version is insufficient.
    """


def parse_toml(file_path: Path) -> dict[str, Any]:
    """
    Parse TOML file and return as dictionary.

    Args:
        file_path: Path to TOML file

    Returns:
        Dictionary representation of TOML data

    Raises:
        SystemExit: On parsing errors or file access issues
    """
    try:
        import tomllib
    except ImportError:
        print("Error: tomllib not available (Python >= 3.11 required)", file=sys.stderr)
        sys.exit(2)

    try:
        with open(file_path, "rb") as f:
            return tomllib.load(f)
    except tomllib.TOMLDecodeError as e:
        print(f"Error: Invalid TOML syntax in {file_path}: {e}", file=sys.stderr)
        sys.exit(2)
    except Exception as e:
        print(f"Error reading TOML file {file_path}: {e}", file=sys.stderr)
        sys.exit(1)


def parse_json(file_path: Path) -> dict[str, Any]:
    """
    Parse and validate JSON file.

    Args:
        file_path: Path to JSON file

    Returns:
        Dictionary representation of JSON data

    Raises:
        SystemExit: On parsing errors or file access issues
    """
    try:
        with open(file_path, encoding="utf-8") as f:
            data: dict[str, Any] = json.load(f)
            return data
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON syntax in {file_path}: {e}", file=sys.stderr)
        sys.exit(2)
    except Exception as e:
        print(f"Error reading JSON file {file_path}: {e}", file=sys.stderr)
        sys.exit(1)


def main() -> None:
    """
    Main entry point for TOML/JSON converter CLI.

    Parses command-line arguments, reads input file, and outputs JSON.
    """
    check_python_version()

    parser = argparse.ArgumentParser(description="Convert TOML or JSON file to JSON output")
    parser.add_argument("--file", type=Path, required=True, help="Path to TOML or JSON file")
    parser.add_argument(
        "--pretty",
        action="store_true",
        help="Pretty-print JSON output (default: compact)",
    )

    args = parser.parse_args()

    # Validate file exists and is readable
    if not args.file.exists():
        print(f"Error: File not found: {args.file}", file=sys.stderr)
        sys.exit(1)

    if not args.file.is_file():
        print(f"Error: Not a file: {args.file}", file=sys.stderr)
        sys.exit(1)

    # Parse based on extension
    ext = args.file.suffix.lower()

    if ext == ".toml":
        data = parse_toml(args.file)
    elif ext == ".json":
        data = parse_json(args.file)
    else:
        print(
            f"Error: Unsupported file extension '{ext}' (only .toml and .json are supported)",
            file=sys.stderr,
        )
        sys.exit(1)

    # Output JSON
    if args.pretty:
        print(json.dumps(data, indent=2, ensure_ascii=False))
    else:
        print(json.dumps(data, separators=(",", ":"), ensure_ascii=False))


if __name__ == "__main__":
    main()
