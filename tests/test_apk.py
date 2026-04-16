"""Tests for scripts/utils/apk.py."""

# ruff: noqa: S101, ARG001, ARG002, RUF043, S108
from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from scripts.utils.apk import (
    AAPT2Manager,
    BundleType,
    SplitAPKHandler,
    _validate_apk_path,
    _validate_path,
    detect_bundle_type,
)

# ---------------------------------------------------------------------------
# _validate_path
# ---------------------------------------------------------------------------


class TestValidatePath:
    def test_returns_true_for_normal_path(self, tmp_path: Path) -> None:
        assert _validate_path(tmp_path / "file.apk") is True

    def test_returns_false_on_os_error(self) -> None:
        # Path with null byte triggers OSError on resolve()
        result = _validate_path(Path("/tmp/\x00bad"))
        assert result is False

    def test_base_dir_allows_child(self, tmp_path: Path) -> None:
        child = tmp_path / "a" / "b.apk"
        assert _validate_path(child, tmp_path) is True

    def test_base_dir_rejects_traversal(self, tmp_path: Path) -> None:
        outside = tmp_path.parent / "other.apk"
        assert _validate_path(outside, tmp_path) is False


# ---------------------------------------------------------------------------
# _validate_apk_path
# ---------------------------------------------------------------------------


class TestValidateApkPath:
    def test_accepts_apk_extension(self, tmp_path: Path) -> None:
        _validate_apk_path(tmp_path / "app.apk", "test")  # must not raise

    def test_rejects_non_apk_extension(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError, match=".apk"):
            _validate_apk_path(tmp_path / "app.zip", "test")

    def test_rejects_non_path_object(self) -> None:
        with pytest.raises((ValueError, AttributeError)):
            _validate_apk_path("app.apk", "test")  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# detect_bundle_type
# ---------------------------------------------------------------------------


class TestDetectBundleType:
    def test_missing_file_returns_unknown(self, tmp_path: Path) -> None:
        assert detect_bundle_type(tmp_path / "missing.apk") == BundleType.UNKNOWN

    def test_apk_extension(self, tmp_path: Path) -> None:
        f = tmp_path / "app.apk"
        f.write_bytes(b"\x00")
        assert detect_bundle_type(f) == BundleType.APK

    def test_xapk_extension(self, tmp_path: Path) -> None:
        f = tmp_path / "app.xapk"
        f.write_bytes(b"\x00")
        assert detect_bundle_type(f) == BundleType.XAPK

    def test_apkm_extension(self, tmp_path: Path) -> None:
        f = tmp_path / "app.apkm"
        f.write_bytes(b"\x00")
        assert detect_bundle_type(f) == BundleType.APKM

    def test_zip_magic_no_extension(self, tmp_path: Path) -> None:
        f = tmp_path / "app.bin"
        f.write_bytes(b"PK\x03\x04" + b"\x00" * 26)
        assert detect_bundle_type(f) == BundleType.APK

    def test_unknown_bytes_no_extension(self, tmp_path: Path) -> None:
        f = tmp_path / "app.bin"
        f.write_bytes(b"\xff\xfe\xfd\xfc")
        assert detect_bundle_type(f) == BundleType.UNKNOWN


# ---------------------------------------------------------------------------
# SplitAPKHandler
# ---------------------------------------------------------------------------


class TestSplitAPKHandler:
    def test_detect_bundle_type_delegates(self, tmp_path: Path) -> None:
        handler = SplitAPKHandler()
        f = tmp_path / "test.apk"
        f.write_bytes(b"\x00")
        assert handler.detect_bundle_type(f) == BundleType.APK

    def test_merge_splits_copies_apk_directly(self, tmp_path: Path, sample_apk: Path) -> None:
        output = tmp_path / "out.apk"
        handler = SplitAPKHandler()
        result = handler.merge_splits(sample_apk, output)
        assert result is True
        assert output.exists()

    def test_merge_splits_unknown_returns_false(self, tmp_path: Path) -> None:
        bundle = tmp_path / "app.bin"
        bundle.write_bytes(b"\xff\xfe")
        output = tmp_path / "out.apk"
        handler = SplitAPKHandler()
        assert handler.merge_splits(bundle, output) is False

    def test_extract_splits_returns_empty_for_missing(self, tmp_path: Path) -> None:
        handler = SplitAPKHandler()
        result = handler.extract_splits(tmp_path / "missing.xapk", tmp_path / "out")
        assert result == []

    def test_extract_splits_from_xapk(self, tmp_path: Path, sample_xapk: Path) -> None:
        out_dir = tmp_path / "splits"
        handler = SplitAPKHandler()
        splits = handler.extract_splits(sample_xapk, out_dir)
        assert len(splits) == 2
        for split in splits:
            assert split.suffix == ".apk"

    def test_extract_splits_bad_zip_returns_empty(self, tmp_path: Path) -> None:
        bundle = tmp_path / "bad.xapk"
        bundle.write_bytes(b"not a zip")
        handler = SplitAPKHandler()
        result = handler.extract_splits(bundle, tmp_path / "out")
        assert result == []

    def test_find_apkeditor_none_when_missing(self, tmp_path: Path) -> None:
        handler = SplitAPKHandler()
        # Force search in a directory where no jar exists
        with patch.object(Path, "exists", return_value=False):
            jar = handler._find_apkeditor()
        assert jar is None


# ---------------------------------------------------------------------------
# AAPT2Manager
# ---------------------------------------------------------------------------


class TestAAPT2Manager:
    def test_init_creates_cache_dir(self, tmp_path: Path) -> None:
        cache = tmp_path / "aapt2_cache"
        mgr = AAPT2Manager(cache_dir=cache)
        assert cache.is_dir()
        assert mgr.cache_dir == cache

    def test_get_aapt2_returns_cached_binary(self, tmp_path: Path) -> None:
        cache = tmp_path / "aapt2"
        cache.mkdir()
        binary = cache / "aapt2-arm64-v8a"
        binary.write_bytes(b"fake")
        mgr = AAPT2Manager(cache_dir=cache)
        result = mgr.get_aapt2("arm64-v8a")
        assert result == binary

    def test_get_aapt2_returns_none_when_unavailable(self, tmp_path: Path) -> None:
        cache = tmp_path / "aapt2"
        cache.mkdir()
        mgr = AAPT2Manager(cache_dir=cache)
        with (
            patch("scripts.utils.apk.AAPT2Manager.get_aapt2", wraps=mgr.get_aapt2),
            patch("scripts.utils.network.gh_dl", return_value=False),
            patch("shutil.which", return_value=None),
        ):
            result = mgr.get_aapt2("arm64-v8a")
        assert result is None

    def test_optimize_apk_returns_false_when_no_input(self, tmp_path: Path) -> None:
        mgr = AAPT2Manager(cache_dir=tmp_path / "aapt2")
        result = mgr.optimize_apk(tmp_path / "missing.apk", tmp_path / "out.apk")
        assert result is False

    def test_optimize_apk_returns_false_when_no_aapt2(self, tmp_path: Path, sample_apk: Path) -> None:
        mgr = AAPT2Manager(cache_dir=tmp_path / "aapt2")
        with patch.object(mgr, "get_aapt2", return_value=None):
            result = mgr.optimize_apk(sample_apk, tmp_path / "out.apk")
        assert result is False

    def test_optimize_apk_passes_language_and_density(self, tmp_path: Path, sample_apk: Path) -> None:
        mgr = AAPT2Manager(cache_dir=tmp_path / "aapt2")
        fake_bin = tmp_path / "aapt2_bin"
        fake_bin.write_bytes(b"fake")
        fake_bin.chmod(0o755)

        captured_cmd: list[list[str]] = []

        def capture_run(cmd: list[str], **kwargs: object) -> MagicMock:
            captured_cmd.append(cmd)
            return MagicMock(returncode=0)

        with (
            patch.object(mgr, "get_aapt2", return_value=fake_bin),
            patch("subprocess.run", side_effect=capture_run),
        ):
            mgr.optimize_apk(
                sample_apk,
                tmp_path / "out.apk",
                languages=["en"],
                densities=["xxhdpi"],
            )

        assert len(captured_cmd) == 1
        cmd = captured_cmd[0]
        assert "--target-locales" in cmd
        assert "en" in cmd
        assert "--target-densities" in cmd
        assert "xxhdpi" in cmd

    def test_optimize_apk_subprocess_failure(self, tmp_path: Path, sample_apk: Path) -> None:
        mgr = AAPT2Manager(cache_dir=tmp_path / "aapt2")
        fake_bin = tmp_path / "aapt2_bin"
        fake_bin.write_bytes(b"fake")
        fake_bin.chmod(0o755)

        with (
            patch.object(mgr, "get_aapt2", return_value=fake_bin),
            patch(
                "subprocess.run",
                side_effect=subprocess.CalledProcessError(1, "aapt2"),
            ) as mock_run,
        ):
            result = mgr.optimize_apk(sample_apk, tmp_path / "out.apk")
        assert result is False
        mock_run.assert_called_once()
        assert mock_run.call_args.kwargs.get("check") is True
