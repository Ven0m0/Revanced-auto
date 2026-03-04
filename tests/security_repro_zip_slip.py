"""Reproduction script for zip slip vulnerability."""

from __future__ import annotations

import sys
import zipfile
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import TypedDict


class ZipEntryType(Enum):
    """Types of zip slip payloads."""

    RELATIVE_PATH = "relative_path"
    ABSOLUTE_PATH = "absolute_path"
    NORMAL = "normal"


class ZipSlipPayload(TypedDict):
    """Zip slip payload definition.

    Attributes:
        name: Entry name in the zip.
        content: Content of the entry.
        type_: Type of entry (for categorization).

    """

    name: str
    content: str
    type_: str


@dataclass(frozen=True, slots=True)
class ZipSlipConfig:
    """Configuration for creating zip slip payloads.

    Attributes:
        include_relative: Include relative path traversal.
        include_absolute: Include absolute path traversal.
        include_normal: Include normal file entry.

    """

    include_relative: bool = True
    include_absolute: bool = False  # Often blocked by zipfile
    include_normal: bool = True


def create_zip_slim_payloads(config: ZipSlipConfig | None = None) -> list[ZipSlipPayload]:
    """Create zip slip payloads based on configuration.

    Args:
        config: Configuration for payloads. Defaults to all enabled except absolute.

    Returns:
        List of zip slip payloads.

    """
    cfg = config or ZipSlipConfig()
    payloads: list[ZipSlipPayload] = []

    if cfg.include_relative:
        payloads.append(
            {
                "name": "../evil.txt",
                "content": "evil content - relative path traversal",
                "type_": ZipEntryType.RELATIVE_PATH.value,
            }
        )

    if cfg.include_absolute:
        payloads.append(
            {
                "name": "/tmp/evil_abs.txt",
                "content": "evil content - absolute path",
                "type_": ZipEntryType.ABSOLUTE_PATH.value,
            }
        )

    if cfg.include_normal:
        payloads.append(
            {
                "name": "good.txt",
                "content": "good content - normal file",
                "type_": ZipEntryType.NORMAL.value,
            }
        )

    return payloads


def create_zip(filename: Path | str, payloads: list[ZipSlipPayload] | None = None) -> None:
    """Create a zip file with zip slip payloads.

    Args:
        filename: The output filename.
        payloads: List of payloads to include. Defaults to standard set.

    """
    path = Path(filename)
    entries = payloads or create_zip_slim_payloads()

    with zipfile.ZipFile(path, "w") as zf:
        for entry in entries:
            zf.writestr(entry["name"], entry["content"])


def extract_safely(zip_path: Path | str, extract_dir: Path | str) -> list[str]:
    """Safely extract zip file, filtering out suspicious entries.

    Args:
        zip_path: Path to zip file.
        extract_dir: Directory to extract to.

    Returns:
        List of extracted (safe) filenames.

    Raises:
        ValueError: If zip contains unsafe entries.

    """
    safe_entries: list[str] = []
    extract_path = Path(extract_dir)

    with zipfile.ZipFile(zip_path, "r") as zf:
        for entry in zf.namelist():
            # Check for path traversal
            target = (extract_path / entry).resolve()
            if not str(target).startswith(str(extract_path.resolve())):
                raise ValueError(f"Unsafe entry detected: {entry}")
            safe_entries.append(entry)

        zf.extractall(extract_path)

    return safe_entries


def main(args: list[str] | None = None) -> int:
    """Main entry point for zip slip reproduction.

    Args:
        args: Command line arguments.

    Returns:
        Exit code.

    """
    argv = args if args is not None else sys.argv[1:]

    if not argv:
        print("Usage: python security_repro_zip_slip.py <output.zip>", file=sys.stderr)
        print("Creates a zip file with path traversal payloads for security testing.", file=sys.stderr)
        return 1

    filename = Path(argv[0])

    try:
        create_zip(filename)
        print(f"Created {filename} with zip slip payloads")

        # Show contents
        with zipfile.ZipFile(filename, "r") as zf:
            print("Contents:")
            for info in zf.infolist():
                print(f"  {info.filename}: {info.file_size} bytes")

        return 0

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
