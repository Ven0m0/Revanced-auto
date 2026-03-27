"""Tests for scripts/builder/notifier.py."""

# ruff: noqa: D101, D102, S101, SLF001, PLC0415, TC003

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from scripts.builder.notifier import (
    AppriseNotifier,
    BuildNotification,
    GitHubReleaseNotifier,
    NotificationConfig,
    NotifierFactory,
    NullNotifier,
    TelegramNotifier,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def success_notification(tmp_path: Path) -> BuildNotification:
    """A successful build notification."""
    apk = tmp_path / "app.apk"
    apk.write_bytes(b"\x00")
    return BuildNotification(
        app_name="YouTube",
        brand="ReVanced",
        version="18.0.0",
        arch="arm64-v8a",
        output_path=apk,
        success=True,
        changelog="Patched with ReVanced",
    )


@pytest.fixture
def failure_notification(tmp_path: Path) -> BuildNotification:
    """A failed build notification."""
    return BuildNotification(
        app_name="YouTube",
        brand="ReVanced",
        version="18.0.0",
        arch="arm64-v8a",
        output_path=tmp_path / "app.apk",
        success=False,
        changelog="",
        error="Patch failed",
    )


# ---------------------------------------------------------------------------
# NotificationConfig
# ---------------------------------------------------------------------------


class TestNotificationConfig:
    def test_get_returns_default_when_missing(self) -> None:
        cfg = NotificationConfig({})
        assert cfg.get("missing_key", "default") == "default"

    def test_env_var_substitution_dollar_brace(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("MY_TOKEN", "abc123")
        cfg = NotificationConfig({"token": "${MY_TOKEN}"})
        assert cfg.get("token") == "abc123"

    def test_env_var_substitution_dollar_name(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("MY_TOKEN", "xyz")
        cfg = NotificationConfig({"token": "$MY_TOKEN"})
        assert cfg.get("token") == "xyz"

    def test_env_var_not_set_keeps_original(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("UNDEFINED_VAR", raising=False)
        cfg = NotificationConfig({"token": "${UNDEFINED_VAR}"})
        assert cfg.get("token") == "${UNDEFINED_VAR}"

    def test_notifier_type_defaults_to_null(self) -> None:
        assert NotificationConfig({}).notifier_type == "null"

    def test_notifier_type_from_config(self) -> None:
        cfg = NotificationConfig({"type": "telegram"})
        assert cfg.notifier_type == "telegram"


# ---------------------------------------------------------------------------
# NullNotifier
# ---------------------------------------------------------------------------


class TestNullNotifier:
    def test_send_always_returns_true(self, success_notification: BuildNotification) -> None:
        assert NullNotifier().send(success_notification) is True

    def test_send_failure_notification_returns_true(self, failure_notification: BuildNotification) -> None:
        assert NullNotifier().send(failure_notification) is True


# ---------------------------------------------------------------------------
# TelegramNotifier
# ---------------------------------------------------------------------------


class TestTelegramNotifier:
    def test_send_returns_true_on_200(self, success_notification: BuildNotification) -> None:
        notifier = TelegramNotifier("fake_token", "fake_chat")
        mock_response = MagicMock()
        mock_response.status_code = 200

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value = mock_client

            result = notifier.send(success_notification)

        assert result is True

    def test_send_returns_false_on_http_error(self, success_notification: BuildNotification) -> None:
        import httpx

        notifier = TelegramNotifier("fake_token", "fake_chat")

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.post = AsyncMock(side_effect=httpx.HTTPError("error"))
            mock_client_cls.return_value = mock_client

            result = notifier.send(success_notification)

        assert result is False

    def test_format_message_includes_app_name(self, success_notification: BuildNotification) -> None:
        notifier = TelegramNotifier("token", "chat")
        msg = notifier._format_message(success_notification)
        assert "YouTube" in msg

    def test_format_message_includes_error(self, failure_notification: BuildNotification) -> None:
        notifier = TelegramNotifier("token", "chat")
        msg = notifier._format_message(failure_notification)
        assert "Patch failed" in msg


# ---------------------------------------------------------------------------
# AppriseNotifier
# ---------------------------------------------------------------------------


class TestAppriseNotifier:
    def test_send_returns_true_when_apprise_succeeds(self, success_notification: BuildNotification) -> None:
        mock_apprise = MagicMock()
        mock_apprise.notify.return_value = True

        with patch.dict("sys.modules", {"apprise": MagicMock(Apprise=MagicMock(return_value=mock_apprise))}):
            notifier = AppriseNotifier("tgram://token/chat")
            result = notifier.send(success_notification)

        assert result is True

    def test_send_returns_false_on_import_error(self, success_notification: BuildNotification) -> None:
        with patch.dict("sys.modules", {"apprise": None}):
            notifier = AppriseNotifier("tgram://token/chat")
            result = notifier.send(success_notification)

        assert result is False


# ---------------------------------------------------------------------------
# GitHubReleaseNotifier
# ---------------------------------------------------------------------------


class TestGitHubReleaseNotifier:
    def test_send_returns_false_for_failure_notification(self, failure_notification: BuildNotification) -> None:
        notifier = GitHubReleaseNotifier("owner/repo", "ghp_token")
        assert notifier.send(failure_notification) is False

    def test_send_creates_release_on_success(
        self, success_notification: BuildNotification
    ) -> None:
        notifier = GitHubReleaseNotifier("owner/repo", "ghp_token")

        with patch.object(notifier, "create_release", return_value="https://github.com/owner/repo/releases/1") as mock:
            result = notifier.send(success_notification)

        assert result is True
        mock.assert_called_once()

    def test_send_returns_false_when_create_release_fails(
        self, success_notification: BuildNotification
    ) -> None:
        notifier = GitHubReleaseNotifier("owner/repo", "ghp_token")

        with patch.object(notifier, "create_release", return_value=""):
            result = notifier.send(success_notification)

        assert result is False

    def test_upload_asset_returns_false_on_error(self, tmp_path: Path) -> None:
        import httpx

        notifier = GitHubReleaseNotifier("owner/repo", "ghp_token")
        artifact = tmp_path / "app.apk"
        artifact.write_bytes(b"\x00")

        with patch("httpx.post", side_effect=httpx.HTTPError("err")):
            result = notifier._upload_asset("https://upload.url", "app.apk", artifact)

        assert result is False


# ---------------------------------------------------------------------------
# NotifierFactory
# ---------------------------------------------------------------------------


class TestNotifierFactory:
    def test_creates_null_notifier(self) -> None:
        cfg = NotificationConfig({"type": "null"})
        notifier = NotifierFactory.create(cfg)
        assert isinstance(notifier, NullNotifier)

    def test_creates_telegram_notifier(self) -> None:
        cfg = NotificationConfig({
            "type": "telegram",
            "telegram_bot_token": "tok",
            "telegram_chat_id": "chat",
        })
        notifier = NotifierFactory.create(cfg)
        assert isinstance(notifier, TelegramNotifier)

    def test_creates_apprise_notifier(self) -> None:
        cfg = NotificationConfig({"type": "apprise", "apprise_url": "discord://hook"})
        notifier = NotifierFactory.create(cfg)
        assert isinstance(notifier, AppriseNotifier)

    def test_creates_github_notifier(self) -> None:
        cfg = NotificationConfig({
            "type": "github",
            "github_repo": "owner/repo",
            "github_token": "ghp_token",
        })
        notifier = NotifierFactory.create(cfg)
        assert isinstance(notifier, GitHubReleaseNotifier)

    def test_raises_on_unknown_type(self) -> None:
        cfg = NotificationConfig({"type": "unknown_service"})
        with pytest.raises(ValueError, match="Unknown notifier type"):
            NotifierFactory.create(cfg)

    def test_raises_telegram_missing_token(self) -> None:
        cfg = NotificationConfig({"type": "telegram"})
        with pytest.raises(ValueError, match="telegram_bot_token"):
            NotifierFactory.create(cfg)

    def test_raises_apprise_missing_url(self) -> None:
        cfg = NotificationConfig({"type": "apprise"})
        with pytest.raises(ValueError, match="apprise_url"):
            NotifierFactory.create(cfg)

    def test_accepts_dict_config(self) -> None:
        notifier = NotifierFactory.create({"type": "null"})
        assert isinstance(notifier, NullNotifier)
