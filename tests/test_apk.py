"""Tests for scripts/utils/apk.py."""

# ruff: noqa: S101, ARG002, RUF043, S108
from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from scripts.utils.apk import (
    APKSigner,
    BundleType,
    SplitAPKHandler,
    _validate_apk_path,
    _validate_path,
    align_apk,
    detect_bundle_type,
)

# ---------------------------------------------------------------------------
# APKSigner
# ---------------------------------------------------------------------------


class TestAPKSigner:
    @pytest.fixture(autouse=True)
    def _jar_present(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("scripts.utils.apk._ensure_apksigner_jar", lambda: True)

    def _signer(self) -> APKSigner:
        return APKSigner(Path("ks.keystore"), "storepw", "morphe", "keypw")

    def test_missing_jar_fails_without_running_java(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("scripts.utils.apk._ensure_apksigner_jar", lambda: False)
        with patch("subprocess.run") as mock_run:
            assert self._signer().sign(Path("in.apk"), Path("out.apk")) is False
        mock_run.assert_not_called()

    def test_runs_pinned_apksigner_jar_with_v1_v2_only(self) -> None:
        with patch("subprocess.run") as mock_run:
            assert self._signer().sign(Path("in.apk"), Path("out.apk")) is True

        cmd = mock_run.call_args.args[0]
        assert cmd[0] == "java"
        assert cmd[cmd.index("-jar") + 1] == str(Path("bin/apksigner.jar"))
        assert cmd[cmd.index("-jar") + 2] == "sign"
        assert cmd[cmd.index("--v1-signing-enabled") + 1] == "true"
        assert cmd[cmd.index("--v2-signing-enabled") + 1] == "true"
        assert cmd[cmd.index("--v3-signing-enabled") + 1] == "false"
        assert cmd[cmd.index("--v4-signing-enabled") + 1] == "false"
        assert cmd[cmd.index("--ks-key-alias") + 1] == "morphe"
        assert cmd[cmd.index("--out") + 1] == "out.apk"
        assert cmd[-1] == "in.apk"

    def test_failure_logs_stderr_but_never_passwords(self, caplog: pytest.LogCaptureFixture) -> None:
        err = subprocess.CalledProcessError(1, ["java"], stderr="bad key")
        with patch("subprocess.run", side_effect=err):
            assert self._signer().sign(Path("in.apk"), Path("out.apk")) is False

        assert "bad key" in caplog.text
        assert "storepw" not in caplog.text
        assert "keypw" not in caplog.text

    def test_missing_java_returns_false(self) -> None:
        with patch("subprocess.run", side_effect=FileNotFoundError("java")):
            assert self._signer().sign(Path("in.apk"), Path("out.apk")) is False


# ---------------------------------------------------------------------------
# _validate_path
# ---------------------------------------------------------------------------


class TestValidatePath:
    def test_returns_true_for_normal_path(self, tmp_path: Path) -> None:
        assert _validate_path(tmp_path / "file.apk") is True

    def test_returns_false_on_os_error(self) -> None:
        with patch("pathlib.Path.resolve", side_effect=OSError("bad path")):
            result = _validate_path(Path("/tmp/bad"))
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
            _validate_apk_path("app.apk", "test")  # type: ignore  # noqa: PGH003


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
        with patch.object(Path, "exists", return_value=False):
            jar = handler._find_apkeditor()
        assert jar is None

    def test_extract_splits_skips_malicious_paths(self, tmp_path: Path) -> None:
        import zipfile

        bundle = tmp_path / "malicious.xapk"
        out_dir = tmp_path / "out"
        out_dir.mkdir()

        with zipfile.ZipFile(bundle, "w") as zf:
            # zipfile.ZipInfo objects can have absolute or traversal paths
            info = zipfile.ZipInfo("../evil.apk")
            zf.writestr(info, b"evil content")
            zf.writestr("good.apk", b"good content")

        handler = SplitAPKHandler()
        splits = handler.extract_splits(bundle, out_dir)

        # Should only contain good.apk, evil.apk should be skipped
        assert len(splits) == 1
        assert splits[0].name == "good.apk"
        assert not (tmp_path / "evil.apk").exists()


# ---------------------------------------------------------------------------
# align_apk
# ---------------------------------------------------------------------------


class TestAlignApk:
    def test_align_apk_success(self, tmp_path: Path, sample_apk: Path) -> None:
        output = tmp_path / "aligned.apk"
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            result = align_apk(sample_apk, output)
            assert result is True
            mock_run.assert_called_once()
            args, _ = mock_run.call_args
            cmd = args[0]
            assert "zipalign" in cmd
            assert str(sample_apk) in cmd
            assert str(output) in cmd

    def test_align_apk_missing_input(self, tmp_path: Path) -> None:
        input_path = tmp_path / "missing.apk"
        output_path = tmp_path / "aligned.apk"
        result = align_apk(input_path, output_path)
        assert result is False

    def test_align_apk_subprocess_error(self, tmp_path: Path, sample_apk: Path) -> None:
        output = tmp_path / "aligned.apk"
        with patch("subprocess.run", side_effect=subprocess.CalledProcessError(1, "zipalign")):
            result = align_apk(sample_apk, output)
            assert result is False

    def test_align_apk_invalid_extension(self, tmp_path: Path) -> None:
        input_path = tmp_path / "input.zip"
        output_path = tmp_path / "output.apk"
        with pytest.raises(ValueError, match="align_apk input: file must have .apk extension"):
            align_apk(input_path, output_path)


class TestEnsureApksignerJar:
    def test_missing_jar_is_fetched_with_pinned_hash(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        from scripts.lib import env_check
        from scripts.utils import apk

        jar = tmp_path / "bin" / "apksigner.jar"
        monkeypatch.setattr(apk, "APKSIGNER_JAR", jar)
        calls: list[tuple[str, Path, str | None]] = []

        def fake_download(url: str, target: Path, *, sha256: str | None = None) -> bool:
            calls.append((url, target, sha256))
            target.write_bytes(b"jar")
            return True

        monkeypatch.setattr(env_check, "download_with_lock", fake_download)

        assert apk._ensure_apksigner_jar() is True
        assert calls == [
            (f"{env_check._BINARIES_BASE_URL}/apksigner.jar", jar, env_check._PINNED_BINARIES["apksigner.jar"])
        ]
        assert apk._ensure_apksigner_jar() is True
        assert len(calls) == 1

    def test_download_failure_returns_false(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        from scripts.lib import env_check
        from scripts.utils import apk

        monkeypatch.setattr(apk, "APKSIGNER_JAR", tmp_path / "bin" / "apksigner.jar")
        monkeypatch.setattr(env_check, "download_with_lock", lambda *_a, **_k: False)

        assert apk._ensure_apksigner_jar() is False
