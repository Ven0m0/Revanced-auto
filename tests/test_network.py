"""Tests for scripts/utils/network.py."""

# ruff: noqa: D101, D102, S101, SLF001, ARG001, S105, TC003

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import httpx
import pytest

from scripts.utils.network import (
    HttpClient,
    HttpClientConfig,
    _get_deterministic_temp_path,
    aria2c_download,
    download_with_aria2c_fallback,
    download_with_lock,
    gh_dl,
    gh_req,
    req,
)

# ---------------------------------------------------------------------------
# HttpClientConfig defaults
# ---------------------------------------------------------------------------


class TestHttpClientConfig:
    def test_default_timeout(self) -> None:
        cfg = HttpClientConfig()
        assert cfg.timeout == 300  # noqa: PLR2004

    def test_default_max_retries(self) -> None:
        cfg = HttpClientConfig()
        assert cfg.max_retries == 4  # noqa: PLR2004

    def test_github_token_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("GITHUB_TOKEN", "test_token")
        cfg = HttpClientConfig()
        assert cfg.github_token == "test_token"

    def test_github_token_none_when_env_missing(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)
        cfg = HttpClientConfig()
        assert cfg.github_token is None


# ---------------------------------------------------------------------------
# _get_deterministic_temp_path
# ---------------------------------------------------------------------------


class TestGetDeterministicTempPath:
    def test_same_output_same_temp(self, tmp_path: Path) -> None:
        p1 = _get_deterministic_temp_path(tmp_path, "/build/app.apk")
        p2 = _get_deterministic_temp_path(tmp_path, "/build/app.apk")
        assert p1 == p2

    def test_different_output_different_temp(self, tmp_path: Path) -> None:
        p1 = _get_deterministic_temp_path(tmp_path, "/build/app1.apk")
        p2 = _get_deterministic_temp_path(tmp_path, "/build/app2.apk")
        assert p1 != p2


# ---------------------------------------------------------------------------
# HttpClient context managers
# ---------------------------------------------------------------------------


class TestHttpClient:
    def test_sync_context_manager(self) -> None:
        with HttpClient() as client:
            assert client is not None

    @pytest.mark.asyncio
    async def test_async_context_manager(self) -> None:
        async with HttpClient() as client:
            assert client is not None

    def test_get_delegates_to_do_request(self) -> None:
        client = HttpClient()
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.text = "hello"
        mock_response.content = b"hello"

        with patch.object(client._sync_client, "request", return_value=mock_response):
            result = client.get("https://example.com")

        assert result == "hello"
        client.close()


# ---------------------------------------------------------------------------
# download_with_lock
# ---------------------------------------------------------------------------


class TestDownloadWithLock:
    def test_returns_true_when_file_exists(self, tmp_path: Path) -> None:
        existing = tmp_path / "existing.apk"
        existing.write_bytes(b"\x00")
        result = download_with_lock("https://example.com/app.apk", existing)
        assert result is True

    def test_returns_false_on_download_failure(self, tmp_path: Path) -> None:
        output = tmp_path / "new.apk"

        with patch("scripts.utils.network.HttpClient") as mock_cls:
            mock_client = MagicMock()
            mock_client.get.side_effect = httpx.HTTPError("network error")
            mock_client.close.return_value = None
            mock_cls.return_value = mock_client

            result = download_with_lock("https://bad.url/app.apk", output, temp_dir=tmp_path)

        assert result is False


# ---------------------------------------------------------------------------
# req, gh_req, gh_dl helpers
# ---------------------------------------------------------------------------


class TestHelperFunctions:
    def test_req_returns_response_text(self) -> None:
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.text = "response body"
        mock_response.content = b"response body"

        with patch("scripts.utils.network.HttpClient") as mock_cls:
            mock_client = MagicMock()
            mock_client.get.return_value = "response body"
            mock_client.close.return_value = None
            mock_cls.return_value = mock_client

            result = req("https://example.com")

        assert result == "response body"

    def test_gh_req_adds_auth_header(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("GITHUB_TOKEN", "ghp_test")
        captured_headers: dict = {}

        def fake_get(url: str, output: object = None, headers: dict | None = None) -> str:
            if headers:
                captured_headers.update(headers)
            return ""

        with patch("scripts.utils.network.HttpClient") as mock_cls:
            mock_client = MagicMock()
            mock_client.get.side_effect = fake_get
            mock_client.close.return_value = None
            mock_cls.return_value = mock_client

            gh_req("https://api.github.com/repos/test/test")

        assert "Authorization" in captured_headers
        assert "ghp_test" in captured_headers["Authorization"]

    def test_gh_dl_calls_download_with_lock(self, tmp_path: Path) -> None:
        output = tmp_path / "cli.jar"
        with patch("scripts.utils.network.download_with_lock", return_value=True) as mock_dl:
            result = gh_dl(output, "https://github.com/releases/download/cli.jar")

        assert result is True
        mock_dl.assert_called_once()


# ---------------------------------------------------------------------------
# aria2c_download
# ---------------------------------------------------------------------------


class TestAria2cDownload:
    def test_returns_false_when_aria2c_not_installed(self, tmp_path: Path) -> None:
        with patch("shutil.which", return_value=None):
            result = aria2c_download(["https://example.com/app.apk"], tmp_path / "app.apk")
        assert result is False

    def test_returns_true_on_zero_returncode(self, tmp_path: Path) -> None:
        output = tmp_path / "app.apk"
        with (
            patch("shutil.which", return_value="/usr/bin/aria2c"),
            patch("subprocess.run") as mock_run,
        ):
            mock_run.return_value = MagicMock(returncode=0)
            result = aria2c_download(["https://example.com/app.apk"], output)

        assert result is True

    def test_returns_false_on_nonzero_returncode(self, tmp_path: Path) -> None:
        output = tmp_path / "app.apk"
        with (
            patch("shutil.which", return_value="/usr/bin/aria2c"),
            patch("subprocess.run") as mock_run,
        ):
            mock_run.return_value = MagicMock(returncode=1)
            result = aria2c_download(["https://example.com/app.apk"], output)

        assert result is False

    def test_returns_false_on_os_error(self, tmp_path: Path) -> None:
        output = tmp_path / "app.apk"
        with (
            patch("shutil.which", return_value="/usr/bin/aria2c"),
            patch("subprocess.run", side_effect=OSError("no such file")),
        ):
            result = aria2c_download(["https://example.com/app.apk"], output)

        assert result is False

    def test_extra_args_are_passed(self, tmp_path: Path) -> None:
        output = tmp_path / "app.apk"
        captured: list[list[str]] = []

        with (
            patch("shutil.which", return_value="/usr/bin/aria2c"),
            patch("subprocess.run") as mock_run,
        ):
            mock_run.return_value = MagicMock(returncode=0)
            mock_run.side_effect = lambda cmd, **_: (captured.append(cmd), MagicMock(returncode=0))[1]
            aria2c_download(["https://example.com/app.apk"], output, extra_args=["--dry-run"])

        assert "--dry-run" in captured[0]


# ---------------------------------------------------------------------------
# download_with_aria2c_fallback
# ---------------------------------------------------------------------------


class TestDownloadWithAria2cFallback:
    def test_prefers_aria2c_when_available(self, tmp_path: Path) -> None:
        output = tmp_path / "app.apk"
        with (
            patch("shutil.which", return_value="/usr/bin/aria2c"),
            patch("scripts.utils.network.aria2c_download", return_value=True) as mock_aria,
            patch("scripts.utils.network.download_with_lock") as mock_lock,
        ):
            result = download_with_aria2c_fallback(["https://example.com/app.apk"], output)

        assert result is True
        mock_aria.assert_called_once()
        mock_lock.assert_not_called()

    def test_falls_back_to_httpx_when_aria2c_missing(self, tmp_path: Path) -> None:
        output = tmp_path / "app.apk"
        with (
            patch("shutil.which", return_value=None),
            patch("scripts.utils.network.download_with_lock", return_value=True) as mock_lock,
        ):
            result = download_with_aria2c_fallback(["https://example.com/app.apk"], output)

        assert result is True
        mock_lock.assert_called_once()

    def test_falls_back_when_aria2c_fails(self, tmp_path: Path) -> None:
        output = tmp_path / "app.apk"
        with (
            patch("shutil.which", return_value="/usr/bin/aria2c"),
            patch("scripts.utils.network.aria2c_download", return_value=False),
            patch("scripts.utils.network.download_with_lock", return_value=True) as mock_lock,
        ):
            result = download_with_aria2c_fallback(["https://example.com/app.apk"], output)

        assert result is True
        mock_lock.assert_called_once()
