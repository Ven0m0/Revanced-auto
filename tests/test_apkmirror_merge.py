"""Tests for scripts/scrapers/apkmirror.py merge_apkm_splits (in-process re-zip and temp-file cleanup)."""

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
        zf.writestr("res/", b"")
        zf.writestr("res/raw/a.bin", b"payload" * 100)


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


def test_merge_stores_every_entry_uncompressed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    bundle = _setup(tmp_path, monkeypatch)
    out = tmp_path / "out.apk"

    assert apkmirror.merge_apkm_splits(tmp_path, bundle, out) is True

    with zipfile.ZipFile(out) as zf:
        assert sorted(zf.namelist()) == ["AndroidManifest.xml", "res/raw/a.bin"]
        assert {i.compress_type for i in zf.infolist()} == {zipfile.ZIP_STORED}
        assert zf.read("res/raw/a.bin") == b"payload" * 100
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
