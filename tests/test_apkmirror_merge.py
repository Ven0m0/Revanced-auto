"""Tests for scripts/scrapers/apkmirror.py merge_apkm_splits (output kept as-is and temp-file cleanup)."""

# ruff: noqa: S101

from __future__ import annotations

import subprocess
import zipfile
from pathlib import Path

import pytest

from scripts.scrapers import apkmirror


def _write_mzip(path: Path) -> None:
    """Build what APKEditor emits: a compressed zip that also holds a directory entry."""
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("AndroidManifest.xml", b"manifest" * 100)
        zf.writestr("res/raw/a.bin", b"payload" * 100)
        zf.writestr("resources.arsc", b"arsc" * 100, compress_type=zipfile.ZIP_STORED)
        zf.writestr("lib/arm64-v8a/liba.so", b"elf" * 100)


def _setup(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *, java_fails: bool = False, mzip: bool = True) -> Path:
    bundle = tmp_path / "stock.apkm"
    bundle.write_bytes(b"bundle")

    def fake_gh_dl(dest: Path, *_args: object, **_kwargs: object) -> bool:
        dest.write_bytes(b"jar")
        return True

    def fake_run(cmd: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        if java_fails:
            raise subprocess.CalledProcessError(1, cmd, stderr="boom")
        if mzip:
            _write_mzip(Path(f"{bundle}.mzip"))
        else:
            Path(f"{bundle}.mzip").write_bytes(b"not a zip")
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr("scripts.utils.network.gh_dl", fake_gh_dl)
    monkeypatch.setattr(apkmirror.subprocess, "run", fake_run)
    return bundle


def _leftovers(bundle: Path) -> list[Path]:
    candidates = [Path(f"{bundle}.mzip"), bundle.with_suffix(".zip")]
    return [p for p in candidates if p.exists()]


def test_merge_keeps_apkeditor_output_as_is(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    bundle = _setup(tmp_path, monkeypatch)
    out = tmp_path / "out.apk"
    expected = tmp_path / "expected.zip"
    _write_mzip(expected)

    assert apkmirror.merge_apkm_splits(tmp_path, bundle, out) is True

    with zipfile.ZipFile(out) as got, zipfile.ZipFile(expected) as want:
        assert [(i.filename, i.compress_type) for i in got.infolist()] == [
            (i.filename, i.compress_type) for i in want.infolist()
        ]
        assert {n: got.read(n) for n in got.namelist()} == {n: want.read(n) for n in want.namelist()}
        assert got.getinfo("resources.arsc").compress_type == zipfile.ZIP_STORED
        assert got.getinfo("res/raw/a.bin").compress_type == zipfile.ZIP_DEFLATED
    assert _leftovers(bundle) == []


def test_java_failure_raises_and_leaves_no_temp_files(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    bundle = _setup(tmp_path, monkeypatch, java_fails=True)

    with pytest.raises(RuntimeError, match="APKEditor failed"):
        apkmirror.merge_apkm_splits(tmp_path, bundle, tmp_path / "out.apk")

    assert _leftovers(bundle) == []
    assert not (tmp_path / "out.apk").exists()


def test_corrupt_merge_output_leaves_no_temp_files(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    bundle = _setup(tmp_path, monkeypatch, mzip=False)

    with pytest.raises(zipfile.BadZipFile):
        apkmirror.merge_apkm_splits(tmp_path, bundle, tmp_path / "out.apk")

    assert _leftovers(bundle) == []
    assert not (tmp_path / "out.apk").exists()
