"""Shared pytest fixtures for the ReVanced Builder test suite."""

# ruff: noqa: TC003
from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture
def sample_apk(tmp_path: Path) -> Path:
    """Create a minimal placeholder .apk file for testing."""
    # Real APK is a ZIP; write a valid PK header so format detection works
    apk = tmp_path / "sample.apk"
    apk.write_bytes(b"PK\x03\x04" + b"\x00" * 26)
    return apk


@pytest.fixture
def sample_xapk(tmp_path: Path) -> Path:
    """Create a minimal placeholder .xapk bundle for testing."""
    import zipfile

    xapk = tmp_path / "sample.xapk"
    with zipfile.ZipFile(xapk, "w") as zf:
        # Minimal contents: two split APKs inside the bundle
        zf.writestr("base.apk", b"PK\x03\x04" + b"\x00" * 26)
        zf.writestr("split_config.arm64_v8a.apk", b"PK\x03\x04" + b"\x00" * 26)
    return xapk
