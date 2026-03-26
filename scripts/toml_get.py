#!/usr/bin/env python3
"""TOML/JSON to JSON converter for ReVanced Builder.

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

from __future__ import annotations

import argparse
import sys
import tomllib
from dataclasses import dataclass
from enum import Enum, auto
from pathlib import Path
from typing import Any, Protocol, TypedDict

import orjson


class FileType(Enum):
    """Supported file types for conversion."""

    TOML = auto()
    JSON = auto()


class Converter(Protocol):
    """Protocol for file converters."""

    def parse(self, file_path: Path) -> dict[str, Any]:
        """Parse file and return dictionary.

        Args:
            file_path: Path to file.

        Returns:
            Dictionary representation of file content.

        Raises:
            SystemExit: On parsing errors.

        """
        ...


class TOMLConverter:
    """Converter for TOML files."""

    @staticmethod
    def parse(file_path: Path) -> dict[str, Any]:
        """Parse TOML file and return as dictionary.

        Args:
            file_path: Path to TOML file.

        Returns:
            Dictionary representation of TOML data.

        Raises:
            SystemExit: On parsing errors or file access issues.

        """
        try:
            with file_path.open("rb") as f:
                return tomllib.load(f)
        except tomllib.TOMLDecodeError as e:
            print(f"Error: Invalid TOML syntax in {file_path}: {e}", file=sys.stderr)
            sys.exit(2)
        except OSError as e:
            print(f"Error reading TOML file {file_path}: {e}", file=sys.stderr)
            sys.exit(1)


class JSONConverter:
    """Converter for JSON files."""

    @staticmethod
    def parse(file_path: Path) -> dict[str, Any]:
        """Parse and validate JSON file.

        Args:
            file_path: Path to JSON file.

        Returns:
            Dictionary representation of JSON data.

        Raises:
            SystemExit: On parsing errors or file access issues.

        """
        try:
            with file_path.open("rb") as f:
                content = f.read()
                return orjson.loads(content)
        except orjson.JSONDecodeError as e:
            print(f"Error: Invalid JSON syntax in {file_path}: {e}", file=sys.stderr)
            sys.exit(2)
        except OSError as e:
            print(f"Error reading JSON file {file_path}: {e}", file=sys.stderr)
            sys.exit(1)


class ConverterRegistry:
    """Registry of file type converters."""

    _converters: dict[FileType, type[Converter]] = {
        FileType.TOML: TOMLConverter,
        FileType.JSON: JSONConverter,
    }

    @classmethod
    def get_converter(cls, file_type: FileType) -> Converter:
        """Get converter for file type.

        Args:
            file_type: Type of file to convert.

        Returns:
            Converter instance.

        """
        return cls._converters[file_type]()


@dataclass(frozen=True, slots=True)
class ConversionConfig:
    """Configuration for file conversion.

    Attributes:
        file_path: Path to input file.
        pretty: Whether to pretty-print output.
        file_type: Detected file type.

    """

    file_path: Path
    pretty: bool
    file_type: FileType

    @classmethod
    def from_args(cls, args: argparse.Namespace) -> ConversionConfig:
        """Create config from CLI arguments.

        Args:
            args: Parsed CLI arguments.

        Returns:
            ConversionConfig instance.

        Raises:
            SystemExit: If file validation fails.

        """
        file_path: Path = args.file

        # Validate file exists and is readable
        if not file_path.exists():
            print(f"Error: File not found: {file_path}", file=sys.stderr)
            sys.exit(1)
        if not file_path.is_file():
            print(f"Error: Not a file: {file_path}", file=sys.stderr)
            sys.exit(1)

        # Detect file type from extension
        ext = file_path.suffix.lower()
        match ext:
            case ".toml":
                file_type = FileType.TOML
            case ".json":
                file_type = FileType.JSON
            case _:
                print(
                    f"Error: Unsupported file extension '{ext}' (only .toml and .json supported)",
                    file=sys.stderr,
                )
                sys.exit(1)

        return cls(
            file_path=file_path,
            pretty=args.pretty,
            file_type=file_type,
        )


class JSONOutput(TypedDict):
    """JSON output structure."""

    data: dict[str, Any]
    success: bool


def serialize_json(data: dict[str, Any], pretty: bool) -> str:
    """Serialize data to JSON string.

    Args:
        data: Dictionary to serialize.
        pretty: Whether to pretty-print.

    Returns:
        JSON string.

    """
    option: int = orjson.OPT_INDENT_2 if pretty else 0
    return orjson.dumps(data, option=option).decode("utf-8")


def convert_file(config: ConversionConfig) -> str:
    """Convert file to JSON.

    Args:
        config: Conversion configuration.

    Returns:
        JSON string output.

    """
    converter = ConverterRegistry.get_converter(config.file_type)
    data = converter.parse(config.file_path)
    return serialize_json(data, config.pretty)


def main() -> int:
    """Main entry point for TOML/JSON converter CLI.

    Returns:
        Exit code: 0 on success, 1 on error.

    """
    parser = argparse.ArgumentParser(description="Convert TOML or JSON file to JSON output")
    parser.add_argument("--file", type=Path, required=True, help="Path to TOML or JSON file")
    parser.add_argument(
        "--pretty",
        action="store_true",
        help="Pretty-print JSON output (default: compact)",
    )
    args = parser.parse_args()

    config = ConversionConfig.from_args(args)

    try:
        output = convert_file(config)
        print(output)
        return 0
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
