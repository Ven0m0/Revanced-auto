"""Notification module for build results via Telegram, Apprise, and GitHub releases."""

from __future__ import annotations

import os
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol, final

import httpx

if TYPE_CHECKING:
    from collections.abc import Generator
    from pathlib import Path


class _GitHubTokenAuth(httpx.Auth):
    """Custom Auth class for GitHub token authentication to prevent token leakage in logs."""

    def __init__(self, token: str) -> None:
        self.token = token

    def auth_flow(
        self, request: httpx.Request
    ) -> Generator[httpx.Request, httpx.Response]:
        request.headers["Authorization"] = f"token {self.token}"
        yield request


@dataclass
class BuildNotification:
    """Data class containing build result information for notifications."""

    app_name: str
    brand: str
    version: str
    arch: str
    output_path: Path
    success: bool
    changelog: str
    error: str | None = None


class NotificationConfig:
    """Configuration for notifier with environment variable substitution."""

    def __init__(self, config_dict: dict | None = None) -> None:
        """Initialize configuration with optional dict."""
        self._config = config_dict or {}

    def get(self, key: str, default: str | None = None) -> str | None:
        """Get config value with environment variable substitution."""
        value = self._config.get(key, default)
        if value is None:
            return None
        return self._substitute_env_vars(str(value))

    def _substitute_env_vars(self, value: str) -> str:
        """Replace ${VAR} or $VAR patterns with environment variable values."""
        pattern = r"\$\{([^}]+)\}|\$([A-Za-z_][A-Za-z0-9_]*)"

        def replacer(match: re.Match) -> str:
            var_name = match.group(1) or match.group(2)
            return os.environ.get(var_name, match.group(0))

        return re.sub(pattern, replacer, value)

    @property
    def notifier_type(self) -> str:
        """Get notifier type from config."""
        return self.get("type", "null") or "null"

    @property
    def telegram_bot_token(self) -> str | None:
        """Get Telegram bot token."""
        return self.get("telegram_bot_token")

    @property
    def telegram_chat_id(self) -> str | None:
        """Get Telegram chat ID."""
        return self.get("telegram_chat_id")

    @property
    def apprise_url(self) -> str | None:
        """Get Apprise URL."""
        return self.get("apprise_url")

    @property
    def github_repo(self) -> str | None:
        """Get GitHub repository (owner/repo)."""
        return self.get("github_repo")

    @property
    def github_token(self) -> str | None:
        """Get GitHub token."""
        return self.get("github_token")


class Notifier(Protocol):
    """Protocol defining the notifier interface."""

    def send(self, notification: BuildNotification) -> bool:
        """Send notification. Returns True on success."""
        ...


class AsyncNotifier(Protocol):
    """Protocol for async notifiers."""

    async def send(self, notification: BuildNotification) -> bool:
        """Send notification asynchronously. Returns True on success."""
        ...


class BaseNotifier(ABC):
    """Abstract base class for notifiers."""

    @abstractmethod
    def send(self, notification: BuildNotification) -> bool:
        """Send notification. Returns True on success."""
        raise NotImplementedError

    def _format_message(self, notification: BuildNotification) -> str:
        """Format build notification as a message string."""
        status = "SUCCESS" if notification.success else "FAILED"
        message = [
            f"Build {status}: {notification.app_name}",
            f"Brand: {notification.brand}",
            f"Version: {notification.version}",
            f"Architecture: {notification.arch}",
        ]
        if notification.success:
            message.append(f"Output: {notification.output_path}")
        if notification.changelog:
            message.append(f"\nChangelog:\n{notification.changelog}")
        if notification.error:
            message.append(f"\nError:\n{notification.error}")
        return "\n".join(message)


@final
class NullNotifier(BaseNotifier):
    """No-op notifier that does nothing."""

    def send(self, notification: BuildNotification) -> bool:
        """Always returns True without sending anything."""
        return True


@final
class TelegramNotifier(BaseNotifier):
    """Notifier that sends messages via Telegram Bot API."""

    def __init__(self, bot_token: str, chat_id: str) -> None:
        """Initialize Telegram notifier.

        Args:
            bot_token: Telegram bot token from @BotFather.
            chat_id: Telegram chat ID to send messages to.
        """
        self._bot_token = bot_token
        self._chat_id = chat_id
        self._api_url = f"https://api.telegram.org/bot{bot_token}"

    async def _async_send(self, notification: BuildNotification) -> bool:
        """Send via Telegram Bot API (async implementation).

        Args:
            notification: Build notification to send.

        Returns:
            True if message was sent successfully, False otherwise.
        """
        message = self._format_message(notification)
        url = f"{self._api_url}/sendMessage"
        payload = {
            "chat_id": self._chat_id,
            "text": message,
            "parse_mode": "HTML",
        }
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(url, json=payload)
                return response.status_code == 200
        except httpx.HTTPError:
            return False

    def send(self, notification: BuildNotification) -> bool:
        """Synchronous wrapper for Telegram notifier."""
        import asyncio

        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(self._async_send(notification))
        return asyncio.run(self._async_send(notification))


@final
class AppriseNotifier(BaseNotifier):
    """Notifier that sends universal notifications via Apprise library."""

    def __init__(self, apprise_url: str) -> None:
        """Initialize Apprise notifier.

        Args:
            apprise_url: Apprise URL(s) for notification services.
        """
        self._apprise_url = apprise_url

    def send(self, notification: BuildNotification) -> bool:
        """Send via Apprise.

        Args:
            notification: Build notification to send.

        Returns:
            True if notification was sent successfully, False otherwise.
        """
        try:
            import apprise

            appr = apprise.Apprise()
            appr.add(self._apprise_url)

            title = f"Build {'SUCCESS' if notification.success else 'FAILED'}: {notification.app_name}"
            body = self._format_message(notification)

            return appr.notify(title=title, body=body)
        except Exception:
            return False


@final
class GitHubReleaseNotifier(BaseNotifier):
    """Notifier that creates GitHub releases."""

    def __init__(self, repo: str, github_token: str) -> None:
        """Initialize GitHub release notifier.

        Args:
            repo: GitHub repository in format 'owner/repo'.
            github_token: GitHub personal access token.
        """
        self._repo = repo
        self._github_token = github_token
        self._api_url = f"https://api.github.com/repos/{repo}"

    def create_release(
        self,
        tag: str,
        body: str,
        artifacts: list[Path],
    ) -> str:
        """Create GitHub release.

        Args:
            tag: Release tag name.
            body: Release body/changelog.
            artifacts: List of artifact paths to upload.

        Returns:
            URL of created release on success, empty string on failure.
        """
        url = f"{self._api_url}/releases"
        headers = {
            "Accept": "application/vnd.github.v3+json",
            "Content-Type": "application/json",
        }
        payload = {
            "tag_name": tag,
            "name": f"Release {tag}",
            "body": body,
            "draft": False,
            "prerelease": False,
        }

        try:
            response = httpx.post(
                url,
                headers=headers,
                json=payload,
                auth=_GitHubTokenAuth(self._github_token),
                timeout=30.0,
            )
            if response.status_code == 201:
                release_data = response.json()
                upload_url = release_data.get("upload_url", "").replace("{?name,label}", "")

                for artifact in artifacts:
                    if artifact.exists():
                        self._upload_asset(
                            upload_url,
                            artifact.name,
                            artifact,
                        )

                return release_data.get("html_url", "")
        except httpx.HTTPError:
            pass
        return ""

    def _upload_asset(
        self,
        upload_url: str,
        filename: str,
        artifact: Path,
    ) -> bool:
        """Upload asset to GitHub release.

        Args:
            upload_url: Upload URL from release creation.
            filename: Name of the asset file.
            artifact: Path to artifact file.

        Returns:
            True if upload was successful, False otherwise.
        """
        headers = {
            "Content-Type": "application/octet-stream",
        }
        params = {"name": filename}

        try:
            with artifact.open("rb") as f:
                response = httpx.post(
                    upload_url,
                    headers=headers,
                    params=params,
                    content=f.read(),
                    auth=_GitHubTokenAuth(self._github_token),
                    timeout=60.0,
                )
                response.raise_for_status()
                return True
        except (httpx.HTTPError, OSError):
            return False

    def send(self, notification: BuildNotification) -> bool:
        """Create GitHub release from build notification.

        Args:
            notification: Build notification to send.

        Returns:
            True if release was created successfully, False otherwise.
        """
        if not notification.success:
            return False

        tag = f"{notification.app_name}-{notification.version}-{notification.arch}"
        body = self._format_message(notification)
        artifacts = [notification.output_path] if notification.output_path.exists() else []

        release_url = self.create_release(tag, body, artifacts)
        return bool(release_url)


class NotifierFactory:
    """Factory class for creating notifier instances based on configuration."""

    @staticmethod
    def create(config: NotificationConfig | dict) -> Notifier:
        """Create appropriate notifier based on config.

        Args:
            config: NotificationConfig instance or dict with notifier settings.

        Returns:
            Configured notifier instance.

        Raises:
            ValueError: If notifier type is unknown or required config is missing.
        """
        if isinstance(config, dict):
            config = NotificationConfig(config)

        notifier_type = config.notifier_type.lower()

        match notifier_type:
            case "null":
                return NullNotifier()
            case "telegram":
                bot_token = config.telegram_bot_token
                chat_id = config.telegram_chat_id
                if not bot_token or not chat_id:
                    msg = "Telegram notifier requires 'telegram_bot_token' and 'telegram_chat_id'"
                    raise ValueError(msg)
                return TelegramNotifier(bot_token, chat_id)
            case "apprise":
                apprise_url = config.apprise_url
                if not apprise_url:
                    msg = "Apprise notifier requires 'apprise_url'"
                    raise ValueError(msg)
                return AppriseNotifier(apprise_url)
            case "github":
                repo = config.github_repo
                token = config.github_token
                if not repo or not token:
                    msg = "GitHub notifier requires 'github_repo' and 'github_token'"
                    raise ValueError(msg)
                return GitHubReleaseNotifier(repo, token)
            case _:
                msg = f"Unknown notifier type: {notifier_type}"
                raise ValueError(msg)
