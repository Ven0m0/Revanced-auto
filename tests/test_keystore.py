"""Tests for scripts/utils/keystore.py."""

# ruff: noqa: S101

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from scripts.utils.keystore import ensure_bks

_BKS_V1_HEADER = b"\x00\x00\x00\x01" + b"\x00" * 12
_BKS_V2_HEADER = b"\x00\x00\x00\x02" + b"\x00" * 12
_PKCS12_HEADER = bytes([0x30, 0x82, 0x0A, 0x00]) + b"\x00" * 12
_JKS_HEADER = b"\xfe\xed\xfe\xed" + b"\x00" * 12
_UNKNOWN_HEADER = b"garbage!" + b"\x00" * 8


class TestEnsureBks:
    @pytest.mark.parametrize("header", [_BKS_V1_HEADER, _BKS_V2_HEADER])
    def test_already_bks_short_circuits(self, tmp_path: Path, header: bytes) -> None:
        """A BKS keystore is returned unchanged; keytool is never invoked."""
        keystore = tmp_path / "ks.keystore"
        keystore.write_bytes(header)

        with patch("subprocess.run") as mock_run:
            result = ensure_bks(keystore, "password")

        assert result == keystore
        mock_run.assert_not_called()

    def test_unrecognized_header_raises(self, tmp_path: Path) -> None:
        keystore = tmp_path / "ks.keystore"
        keystore.write_bytes(_UNKNOWN_HEADER)

        with pytest.raises(ValueError, match="Unrecognized keystore format"):
            ensure_bks(keystore, "password")

    def test_pkcs12_triggers_conversion(self, tmp_path: Path) -> None:
        keystore = tmp_path / "ks.keystore"
        keystore.write_bytes(_PKCS12_HEADER)
        cache_dir = tmp_path / "cache"
        bin_dir = tmp_path / "bin"

        def fake_run(cmd: list[str], **_kwargs: object) -> MagicMock:
            # keytool would have written the destkeystore file; simulate that.
            dest = Path(cmd[cmd.index("-destkeystore") + 1])
            dest.write_bytes(_BKS_V2_HEADER)
            return MagicMock(returncode=0, stderr="")

        with (
            patch("scripts.utils.keystore.download_with_lock", return_value=True) as mock_dl,
            patch("subprocess.run", side_effect=fake_run) as mock_run,
        ):
            result = ensure_bks(keystore, "password", bin_dir=bin_dir, cache_dir=cache_dir)

        mock_dl.assert_called_once()
        assert mock_run.call_count == 1
        cmd = mock_run.call_args.args[0]
        assert "-srcstoretype" in cmd
        assert cmd[cmd.index("-srcstoretype") + 1] == "PKCS12"
        assert cmd[cmd.index("-deststoretype") + 1] == "BKS"
        assert result.suffix == ".bks"
        assert result.read_bytes()[:4] == _BKS_V2_HEADER[:4]

    def test_jks_uses_jks_srcstoretype(self, tmp_path: Path) -> None:
        keystore = tmp_path / "ks.jks"
        keystore.write_bytes(_JKS_HEADER)
        cache_dir = tmp_path / "cache"
        bin_dir = tmp_path / "bin"

        def fake_run(cmd: list[str], **_kwargs: object) -> MagicMock:
            dest = Path(cmd[cmd.index("-destkeystore") + 1])
            dest.write_bytes(_BKS_V2_HEADER)
            return MagicMock(returncode=0, stderr="")

        with (
            patch("scripts.utils.keystore.download_with_lock", return_value=True),
            patch("subprocess.run", side_effect=fake_run) as mock_run,
        ):
            ensure_bks(keystore, "password", bin_dir=bin_dir, cache_dir=cache_dir)

        cmd = mock_run.call_args.args[0]
        assert cmd[cmd.index("-srcstoretype") + 1] == "JKS"

    def test_cached_conversion_is_reused(self, tmp_path: Path) -> None:
        keystore = tmp_path / "ks.keystore"
        keystore.write_bytes(_PKCS12_HEADER)
        cache_dir = tmp_path / "cache"
        bin_dir = tmp_path / "bin"

        def fake_run(cmd: list[str], **_kwargs: object) -> MagicMock:
            dest = Path(cmd[cmd.index("-destkeystore") + 1])
            dest.write_bytes(_BKS_V2_HEADER)
            return MagicMock(returncode=0, stderr="")

        with (
            patch("scripts.utils.keystore.download_with_lock", return_value=True),
            patch("subprocess.run", side_effect=fake_run) as mock_run,
        ):
            first = ensure_bks(keystore, "password", bin_dir=bin_dir, cache_dir=cache_dir)
            second = ensure_bks(keystore, "password", bin_dir=bin_dir, cache_dir=cache_dir)

        assert first == second
        assert mock_run.call_count == 1

    def test_keytool_failure_raises(self, tmp_path: Path) -> None:
        keystore = tmp_path / "ks.keystore"
        keystore.write_bytes(_PKCS12_HEADER)

        with (
            patch("scripts.utils.keystore.download_with_lock", return_value=True),
            patch("subprocess.run", return_value=MagicMock(returncode=1, stderr="bad password")),
            pytest.raises(RuntimeError, match="keytool BKS conversion failed"),
        ):
            ensure_bks(keystore, "password", bin_dir=tmp_path / "bin", cache_dir=tmp_path / "cache")

    def test_bcprov_download_failure_raises(self, tmp_path: Path) -> None:
        keystore = tmp_path / "ks.keystore"
        keystore.write_bytes(_PKCS12_HEADER)

        with (
            patch("scripts.utils.keystore.download_with_lock", return_value=False),
            pytest.raises(RuntimeError, match=r"Failed to download/verify bcprov\.jar"),
        ):
            ensure_bks(keystore, "password", bin_dir=tmp_path / "bin", cache_dir=tmp_path / "cache")
