"""Tests for DownloadManager's central validation, bundle merge, arch and version logic."""

# ruff: noqa: S101, ARG002, TC003
from __future__ import annotations

import asyncio
import io
import zipfile
from pathlib import Path
from typing import Any

import pytest

from scripts.scrapers import download_manager as dm_module
from scripts.scrapers.base import DownloadResult, DownloadSource, ScraperBase, VersionInfo
from scripts.scrapers.download_manager import DownloadManager


def _apk_bytes() -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("AndroidManifest.xml", b"<manifest/>")
    return buf.getvalue()


class _FakeScraper(ScraperBase):
    """Writes chosen bytes on download and records the kwargs it was called with."""

    def __init__(self, source: DownloadSource, payload: bytes = b"", versions: list[str] | None = None) -> None:
        super().__init__(source)
        self.payload = payload
        self.versions = versions or []
        self.download_kwargs: dict[str, Any] = {}
        self.versions_kwargs: dict[str, Any] = {}

    async def get_versions(self, pkg_name: str, **kwargs: object) -> list[VersionInfo]:
        self.versions_kwargs = kwargs
        return [VersionInfo(version=v) for v in self.versions]

    async def download(
        self,
        pkg_name: str,
        version: str | None,
        output_path: Path,
        **kwargs: object,
    ) -> DownloadResult:
        self.download_kwargs = kwargs
        await asyncio.to_thread(output_path.write_bytes, self.payload)
        return DownloadResult(success=True, file_path=output_path, version=version)


def _manager(source: DownloadSource, scraper: _FakeScraper) -> DownloadManager:
    manager = DownloadManager()
    manager._scrapers[source] = scraper
    return manager


def test_html_body_raises_and_is_deleted(tmp_path: Path) -> None:
    source = DownloadSource.APKPURE
    out = tmp_path / "stock.apk"
    manager = _manager(source, _FakeScraper(source, b"<html>Just a moment...</html>"))

    with pytest.raises(RuntimeError, match="non-APK"):
        manager.download("com.example", "1.0", out, source)

    assert not out.exists()


def test_valid_apk_returned(tmp_path: Path) -> None:
    source = DownloadSource.APKPURE
    out = tmp_path / "stock.apk"
    manager = _manager(source, _FakeScraper(source, _apk_bytes()))

    assert manager.download("com.example", "1.0", out, source) == out
    assert out.exists()


def test_bundle_is_merged(tmp_path: Path, sample_xapk: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source = DownloadSource.APKPURE
    out = tmp_path / "stock.apk"
    manager = _manager(source, _FakeScraper(source, sample_xapk.read_bytes()))
    calls: list[tuple[Path, Path]] = []

    def fake_merge(_temp_dir: Path, bundle_path: Path, output_path: Path) -> bool:
        calls.append((bundle_path, output_path))
        output_path.write_bytes(_apk_bytes())
        return True

    monkeypatch.setattr(dm_module, "merge_apkm_splits", fake_merge)

    assert manager.download("com.example", "1.0", out, source) == out
    assert calls == [(out.with_suffix(".apkm"), out)]
    assert not out.with_suffix(".apkm").exists()


@pytest.mark.parametrize(
    ("source", "expected_arch"),
    [
        (DownloadSource.APKMIRROR, "armeabi-v7a"),
        (DownloadSource.GITHUB, "armeabi-v7a"),
        (DownloadSource.UPTODOWN, "armeabi-v7a"),
        (DownloadSource.ARCHIVE, "arm-v7a"),
    ],
)
def test_arch_normalized_except_archive(tmp_path: Path, source: DownloadSource, expected_arch: str) -> None:
    fake = _FakeScraper(source, _apk_bytes())
    manager = _manager(source, fake)

    manager.download("com.example", "1.0", tmp_path / "stock.apk", source, arch="arm-v7a")

    assert fake.download_kwargs["arch"] == expected_arch


def test_apkmirror_download_keeps_exact_beta_version(tmp_path: Path) -> None:
    source = DownloadSource.APKMIRROR
    fake = _FakeScraper(source, _apk_bytes())
    manager = _manager(source, fake)

    manager.download("com.example", "1.0-beta", tmp_path / "stock.apk", source)

    assert fake.download_kwargs["exclude_alpha_beta"] is False


def test_resolve_picks_highest_compatible() -> None:
    source = DownloadSource.APKPURE
    manager = _manager(source, _FakeScraper(source, versions=["3.0.0", "2.0.0", "1.0.0"]))

    assert manager.resolve("com.example", source, compatible=["1.0.0", "2.0.0"]) == ("2.0.0", "2.0.0")


def test_resolve_without_compatible_picks_newest() -> None:
    source = DownloadSource.APKPURE
    manager = _manager(source, _FakeScraper(source, versions=["1.0.0", "3.0.0", "2.0.0"]))

    assert manager.resolve("com.example", source, compatible=[]) == ("3.0.0", "3.0.0")


def test_resolve_no_overlap_raises() -> None:
    source = DownloadSource.APKPURE
    manager = _manager(source, _FakeScraper(source, versions=["3.0.0", "2.0.0"]))

    with pytest.raises(ValueError, match="no patch-compatible version on apkpure"):
        manager.resolve("com.example", source, compatible=["1.0.0"])


@pytest.mark.parametrize(("include_beta", "expect_exclude"), [(False, True), (True, False)])
def test_resolve_passes_include_beta(*, include_beta: bool, expect_exclude: bool) -> None:
    source = DownloadSource.APKMIRROR
    fake = _FakeScraper(source, versions=["1.0.0"])
    manager = _manager(source, fake)

    manager.resolve("com.example", source, include_beta=include_beta)

    assert fake.versions_kwargs["exclude_alpha_beta"] is expect_exclude


@pytest.mark.parametrize(
    ("source", "expected"),
    [(DownloadSource.APKMIRROR, ["1.0.0"]), (DownloadSource.APKPURE, None)],
)
def test_resolve_forwards_compatible_only_to_apkmirror(source: DownloadSource, expected: list[str] | None) -> None:
    fake = _FakeScraper(source, versions=["1.0.0"])
    manager = _manager(source, fake)

    manager.resolve("com.example", source, compatible=["1.0.0"])

    assert fake.versions_kwargs.get("compatible") == expected


def test_expected_cert_match_passes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source = DownloadSource.APKPURE
    out = tmp_path / "stock.apk"
    manager = _manager(source, _FakeScraper(source, _apk_bytes()))
    monkeypatch.setattr(dm_module, "signer_digests", lambda _p: {"abc"})

    assert manager.download("com.example", "1.0", out, source, expected_cert="abc") == out


def test_expected_cert_mismatch_raises_and_deletes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source = DownloadSource.APKPURE
    out = tmp_path / "stock.apk"
    manager = _manager(source, _FakeScraper(source, _apk_bytes()))
    monkeypatch.setattr(dm_module, "signer_digests", lambda _p: {"other"})

    with pytest.raises(RuntimeError, match="signature mismatch"):
        manager.download("com.example", "1.0", out, source, expected_cert="abc")

    assert not out.exists()


def test_bundle_cert_checked_on_base_apk_before_merge(
    tmp_path: Path, sample_xapk: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = DownloadSource.APKPURE
    out = tmp_path / "stock.apk"
    manager = _manager(source, _FakeScraper(source, sample_xapk.read_bytes()))
    checked: list[str] = []
    merged: list[bool] = []

    def fake_verify(path: Path) -> set[str]:
        checked.append(path.name)
        return {"abc"}

    def fake_merge(_temp_dir: Path, _bundle: Path, output_path: Path) -> bool:
        merged.append(bool(checked))
        output_path.write_bytes(_apk_bytes())
        return True

    monkeypatch.setattr(dm_module, "signer_digests", fake_verify)
    monkeypatch.setattr(dm_module, "merge_apkm_splits", fake_merge)

    manager.download("com.example", "1.0", out, source, expected_cert="abc")

    assert checked == ["base.apk"]
    assert merged == [True]


def test_no_expected_cert_skips_verification(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source = DownloadSource.APKPURE
    manager = _manager(source, _FakeScraper(source, _apk_bytes()))

    def boom(_p: Path) -> set[str]:
        pytest.fail("signer_digests must not run")

    monkeypatch.setattr(dm_module, "signer_digests", boom)

    manager.download("com.example", "1.0", tmp_path / "stock.apk", source)
