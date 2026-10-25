"""Tests for scripts/utils/keystore.py."""

# ruff: noqa: S101, S106

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from scripts.utils.keystore import SigningKeystore, ensure_bks, ensure_jdk_readable, prepare_signing

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

    def test_entry_password_used_for_key_passwords(self, tmp_path: Path) -> None:
        keystore = tmp_path / "ks.jks"
        keystore.write_bytes(_JKS_HEADER)

        def fake_run(cmd: list[str], **_kwargs: object) -> MagicMock:
            Path(cmd[cmd.index("-destkeystore") + 1]).write_bytes(_BKS_V2_HEADER)
            return MagicMock(returncode=0, stderr="")

        with (
            patch("scripts.utils.keystore.download_with_lock", return_value=True),
            patch("subprocess.run", side_effect=fake_run) as mock_run,
        ):
            ensure_bks(
                keystore,
                "storepw",
                entry_password="keypw",
                alias="morphe",
                bin_dir=tmp_path / "bin",
                cache_dir=tmp_path / "cache",
            )

        cmd = mock_run.call_args.args[0]
        assert cmd[cmd.index("-srcstorepass") + 1] == "storepw"
        assert cmd[cmd.index("-deststorepass") + 1] == "storepw"
        assert cmd[cmd.index("-srckeypass") + 1] == "keypw"
        assert cmd[cmd.index("-destkeypass") + 1] == "keypw"
        assert cmd[cmd.index("-srcalias") + 1] == "morphe"

    def test_same_entry_password_migrates_whole_store(self, tmp_path: Path) -> None:
        keystore = tmp_path / "ks.jks"
        keystore.write_bytes(_JKS_HEADER)

        def fake_run(cmd: list[str], **_kwargs: object) -> MagicMock:
            Path(cmd[cmd.index("-destkeystore") + 1]).write_bytes(_BKS_V2_HEADER)
            return MagicMock(returncode=0, stderr="")

        with (
            patch("scripts.utils.keystore.download_with_lock", return_value=True),
            patch("subprocess.run", side_effect=fake_run) as mock_run,
        ):
            ensure_bks(
                keystore,
                "pw",
                entry_password="pw",
                alias="morphe",
                bin_dir=tmp_path / "bin",
                cache_dir=tmp_path / "cache",
            )

        cmd = mock_run.call_args.args[0]
        assert "-srckeypass" not in cmd
        assert "-srcalias" not in cmd
        assert cmd[cmd.index("-destkeypass") + 1] == "pw"

    def test_distinct_entry_password_without_alias_raises(self, tmp_path: Path) -> None:
        keystore = tmp_path / "ks.jks"
        keystore.write_bytes(_JKS_HEADER)

        with pytest.raises(ValueError, match="alias is required"):
            ensure_bks(keystore, "storepw", entry_password="keypw", cache_dir=tmp_path / "cache")

    def test_temp_output_is_unique(self, tmp_path: Path) -> None:
        cache_dir = tmp_path / "cache"
        dests: list[Path] = []

        def fake_run(cmd: list[str], **_kwargs: object) -> MagicMock:
            dest = Path(cmd[cmd.index("-destkeystore") + 1])
            dests.append(dest)
            dest.write_bytes(_BKS_V2_HEADER)
            return MagicMock(returncode=0, stderr="")

        with (
            patch("scripts.utils.keystore.download_with_lock", return_value=True),
            patch("subprocess.run", side_effect=fake_run),
        ):
            for i in range(2):
                keystore = tmp_path / f"ks{i}.keystore"
                keystore.write_bytes(_PKCS12_HEADER + bytes([i]))
                ensure_bks(keystore, "password", bin_dir=tmp_path / "bin", cache_dir=cache_dir)

        assert len(dests) == 2
        assert dests[0].parent != dests[1].parent
        assert all(not d.parent.exists() for d in dests)
        assert sorted(p.suffix for p in cache_dir.iterdir()) == [".bks", ".bks"]

    def test_bcprov_download_failure_raises(self, tmp_path: Path) -> None:
        keystore = tmp_path / "ks.keystore"
        keystore.write_bytes(_PKCS12_HEADER)

        with (
            patch("scripts.utils.keystore.download_with_lock", return_value=False),
            pytest.raises(RuntimeError, match=r"Failed to download/verify bcprov\.jar"),
        ):
            ensure_bks(keystore, "password", bin_dir=tmp_path / "bin", cache_dir=tmp_path / "cache")


def _fake_keytool(cmd: list[str], **_kwargs: object) -> MagicMock:
    Path(cmd[cmd.index("-destkeystore") + 1]).write_bytes(_BKS_V2_HEADER)
    return MagicMock(returncode=0, stderr="")


class TestConversionCacheKey:
    def _convert(self, tmp_path: Path, **kwargs: str) -> Path:
        keystore = tmp_path / "ks.jks"
        keystore.write_bytes(_JKS_HEADER)
        with (
            patch("scripts.utils.keystore.download_with_lock", return_value=True),
            patch("subprocess.run", side_effect=_fake_keytool),
        ):
            return ensure_bks(keystore, "storepw", bin_dir=tmp_path / "bin", cache_dir=tmp_path / "cache", **kwargs)

    def test_alias_change_is_not_served_stale(self, tmp_path: Path) -> None:
        first = self._convert(tmp_path, entry_password="keypw", alias="one")
        second = self._convert(tmp_path, entry_password="keypw", alias="two")
        assert first != second

    def test_entry_password_change_is_not_served_stale(self, tmp_path: Path) -> None:
        first = self._convert(tmp_path, entry_password="keypw1", alias="one")
        second = self._convert(tmp_path, entry_password="keypw2", alias="one")
        whole = self._convert(tmp_path)
        assert len({first, second, whole}) == 3

    def test_same_settings_reuse_conversion(self, tmp_path: Path) -> None:
        assert self._convert(tmp_path, entry_password="keypw", alias="one") == self._convert(
            tmp_path, entry_password="keypw", alias="one"
        )

    def test_filename_never_contains_password(self, tmp_path: Path) -> None:
        converted = self._convert(tmp_path, entry_password="keypw", alias="one")
        assert "keypw" not in converted.name
        assert "storepw" not in converted.name


class TestEnsureJdkReadable:
    @pytest.mark.parametrize("header", [_PKCS12_HEADER, _JKS_HEADER])
    def test_non_bks_returned_unchanged(self, tmp_path: Path, header: bytes) -> None:
        keystore = tmp_path / "ks"
        keystore.write_bytes(header)
        with patch("subprocess.run") as mock_run:
            assert ensure_jdk_readable(keystore, "pw") == keystore
        mock_run.assert_not_called()

    @pytest.mark.parametrize(
        ("entry_password", "dest_type"),
        [(None, "PKCS12"), ("storepw", "PKCS12"), ("keypw", "JKS")],
    )
    def test_bks_converted_for_apksigner(self, tmp_path: Path, entry_password: str | None, dest_type: str) -> None:
        keystore = tmp_path / "ks.bks"
        keystore.write_bytes(_BKS_V2_HEADER)
        with (
            patch("scripts.utils.keystore.download_with_lock", return_value=True),
            patch("subprocess.run", side_effect=_fake_keytool) as mock_run,
        ):
            result = ensure_jdk_readable(
                keystore,
                "storepw",
                entry_password=entry_password,
                alias="morphe",
                bin_dir=tmp_path / "bin",
                cache_dir=tmp_path / "cache",
            )

        cmd = mock_run.call_args.args[0]
        assert cmd[cmd.index("-srcstoretype") + 1] == "BKS"
        assert cmd[cmd.index("-deststoretype") + 1] == dest_type
        assert cmd[cmd.index("-providerclass") + 1] == "org.bouncycastle.jce.provider.BouncyCastleProvider"
        assert cmd[cmd.index("-destkeypass") + 1] == (entry_password or "storepw")
        assert result.suffix == f".{dest_type.lower()}"


class TestPrepareSigning:
    def test_entry_password_defaults_to_store_password(self) -> None:
        signing = prepare_signing(None, None, {"KEYSTORE_PASSWORD": "storepw", "KEYSTORE_ENTRY_PASSWORD": ""})
        assert (signing.password, signing.entry_password) == ("storepw", "storepw")

    def test_explicit_entry_password_wins(self) -> None:
        signing = prepare_signing(None, None, {"KEYSTORE_PASSWORD": "storepw", "KEYSTORE_ENTRY_PASSWORD": "keypw"})
        assert (signing.password, signing.entry_password) == ("storepw", "keypw")

    def test_both_unset_use_default(self) -> None:
        assert prepare_signing(None, None, {}) == SigningKeystore("morphe", "Morphe", "Morphe")

    def test_keystore_converted_for_patcher_and_apksigner(self, tmp_path: Path) -> None:
        source = tmp_path / "ks.keystore"
        with (
            patch("scripts.utils.keystore.ensure_bks", return_value=tmp_path / "ks.bks") as bks,
            patch("scripts.utils.keystore.ensure_jdk_readable", return_value=source) as jdk,
        ):
            signing = prepare_signing(source, "custom", {"KEYSTORE_PASSWORD": "pw"})
        assert signing == SigningKeystore("custom", "pw", "pw", tmp_path / "ks.bks", source)
        bks.assert_called_once_with(source, "pw", entry_password="pw", alias="custom")
        jdk.assert_called_once_with(source, "pw", entry_password="pw", alias="custom")
