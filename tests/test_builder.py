"""Tests for the Builder wrapper class."""

# ruff: noqa: S101

from unittest.mock import MagicMock, patch

from scripts.lib.builder import Builder
from scripts.lib.config import Config


def _mock_config() -> MagicMock:
    """Provide a mocked Config instance."""
    config = MagicMock(spec=Config)
    config.config_file = "test_config.toml"
    return config


def test_builder_init() -> None:
    """Test Builder initialization."""
    mock_config = _mock_config()
    builder = Builder(mock_config)
    assert builder.config == mock_config


@patch("scripts.lib.builder.subprocess.run")
def test_builder_build_all_success(mock_run: MagicMock) -> None:
    """Test build_all returns True when subprocess succeeds."""
    mock_config = _mock_config()
    mock_run.return_value = MagicMock(returncode=0)
    builder = Builder(mock_config)

    result = builder.build_all()

    assert result is True
    mock_run.assert_called_once_with(
        ["./build.sh", "test_config.toml"],
        capture_output=True,
        check=False,
        text=True,
    )


@patch("scripts.lib.builder.subprocess.run")
def test_builder_build_all_failure(mock_run: MagicMock) -> None:
    """Test build_all returns False when subprocess fails."""
    mock_config = _mock_config()
    mock_run.return_value = MagicMock(returncode=1)
    builder = Builder(mock_config)

    result = builder.build_all()

    assert result is False
    mock_run.assert_called_once_with(
        ["./build.sh", "test_config.toml"],
        capture_output=True,
        check=False,
        text=True,
    )
