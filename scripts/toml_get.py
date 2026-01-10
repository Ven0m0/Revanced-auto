#!/usr/bin/env python3
"""
TOML/JSON to JSON converter for ReVanced Builder
Converts TOML files to JSON using Python's stdlib tomllib (requires Python >= 3.11)
"""

import sys
import json
import argparse
from pathlib import Path


def check_python_version():
    """Verify Python version is >= 3.11 (required for tomllib)"""
    if sys.version_info < (3, 11):
        print(
            f"Error: Python 3.11 or higher is required (found {sys.version_info.major}.{sys.version_info.minor})",
            file=sys.stderr,
        )
        sys.exit(2)


def parse_toml(file_path: Path) -> dict:
    """Parse TOML file to dict"""
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


def parse_json(file_path: Path) -> dict:
    """Parse and validate JSON file"""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON syntax in {file_path}: {e}", file=sys.stderr)
        sys.exit(2)
    except Exception as e:
        print(f"Error reading JSON file {file_path}: {e}", file=sys.stderr)
        sys.exit(1)


def main():
    check_python_version()

    parser = argparse.ArgumentParser(
        description="Convert TOML or JSON file to JSON output"
    )
    parser.add_argument(
        "--file", type=Path, required=True, help="Path to TOML or JSON file"
    )
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
