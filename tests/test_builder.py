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


@patch("scripts.builder.app_processor.main")
def test_builder_build_all_success(mock_main: MagicMock) -> None:
    """Test build_all returns True when the app processor exits 0."""
    mock_config = _mock_config()
    mock_main.return_value = 0
    builder = Builder(mock_config)

    result = builder.build_all()

    assert result is True
    mock_main.assert_called_once_with(["app_processor.py", "test_config.toml"])


@patch("scripts.builder.app_processor.main")
def test_builder_build_all_failure(mock_main: MagicMock) -> None:
    """Test build_all returns False when the app processor exits non-zero."""
    mock_config = _mock_config()
    mock_main.return_value = 1
    builder = Builder(mock_config)

    result = builder.build_all()

    assert result is False
    mock_main.assert_called_once_with(["app_processor.py", "test_config.toml"])
