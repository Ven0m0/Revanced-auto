"""Reproduction script for zip slip vulnerability."""

import sys
import zipfile


def create_zip(filename: str) -> None:
    """Create a zip file with a zip slip payload.

    Args:
        filename: The output filename.
    """
    with zipfile.ZipFile(filename, "w") as zf:
        # Standard zip slip
        zf.writestr("../evil.txt", "evil content")
        # Absolute path
        # zf.writestr('/tmp/evil_abs.txt', 'evil abs content')  # noqa: ERA001
        # Normal file
        zf.writestr("good.txt", "good content")


if __name__ == "__main__":
    create_zip(sys.argv[1])
