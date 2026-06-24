"""APK I/O helpers for extraction and repackaging.

Provides safe APK extraction and repacking used by the engine pipeline.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import zipfile
from pathlib import Path


def extract_apk(apk: Path, extract_dir: Path) -> bool:
    """Extract APK contents to a directory safely.

    Uses the ``unzip`` CLI when available for performance, otherwise falls back
    to a path-traversal-validated Python extraction.

    Args:
        apk: APK file to extract.
        extract_dir: Destination directory.

    Returns:
        True if extraction succeeded.
    """
    try:
        if shutil.which("unzip"):
            subprocess.run(
                ["unzip", "-o", "-q", str(apk), "-d", str(extract_dir)],
                capture_output=True,
                text=True,
                check=True,
                timeout=300,
            )
            return True

        with zipfile.ZipFile(apk, "r") as zf:
            base_path = extract_dir.resolve()
            for member in zf.infolist():
                member_path = (extract_dir / member.filename).resolve()
                try:
                    member_path.relative_to(base_path)
                except ValueError:
                    raise OSError(f"Illegal file path in APK archive: {member.filename}") from None
            zf.extractall(extract_dir)
        return True
    except (OSError, zipfile.BadZipFile, subprocess.SubprocessError):
        return False


def repack_apk(extract_dir: Path, output_apk: Path) -> bool:
    """Repack extracted APK contents into a new APK.

    Args:
        extract_dir: Directory containing extracted APK contents.
        output_apk: Destination APK path.

    Returns:
        True if repackaging succeeded.
    """
    try:
        output_apk.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(output_apk, "w", zipfile.ZIP_DEFLATED) as zf:
            for root, _dirs, files in os.walk(extract_dir):
                root_path = Path(root)
                for file in files:
                    file_path = root_path / file
                    arcname = str(file_path.relative_to(extract_dir))
                    zf.write(file_path, arcname)
        return True
    except (OSError, zipfile.BadZipFile):
        return False
