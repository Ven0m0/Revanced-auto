"""Shared pytest fixtures for the ReVanced Builder test suite."""

# ruff: noqa: PLC0415, TC003
from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture
def tmp_dir(tmp_path: Path) -> Path:
    """Provide a temporary directory for each test."""
    return tmp_path


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


@pytest.fixture
def sample_toml_config(tmp_path: Path) -> Path:
    """Write a minimal valid config.toml for testing."""
    cfg = tmp_path / "config.toml"
    cfg.write_text(
        """
[global]
parallel-jobs = 1
build-mode = "apk"
patches-version = "latest"
cli-version = "latest"
patches-source = "ReVanced/revanced-patches"

[YouTube]
enabled = true
apkmirror-dlurl = "https://apkmirror.com/apk/google-inc/youtube"
"""
    )
    return cfg
