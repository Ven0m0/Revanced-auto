"""Tests for AppProcessor."""

# ruff: noqa: S101
from unittest.mock import MagicMock

import pytest

from scripts.builder.app_processor import AppProcessor, Architecture
from scripts.builder.config import AppConfig, GlobalConfig


class TestAppProcessor:
    """Test suite for AppProcessor class."""

    def test_parse_architecture(self) -> None:
        """Test _parse_architecture handles all valid arch options and defaults correctly."""
        global_config = GlobalConfig()
        java_runner = MagicMock()
        processor = AppProcessor(global_config, java_runner)

        # Test default (no arch specified)
        config_default = AppConfig(name="TestApp", options={})
        assert processor._parse_architecture(config_default) == Architecture.ALL

        # Test explicit architectures
        valid_archs = [
            ("arm64-v8a", Architecture.ARM64_V8A),
            ("arm-v7a", Architecture.ARM_V7A),
            ("both", Architecture.BOTH),
            ("all", Architecture.ALL),
        ]

        for arch_str, expected_arch in valid_archs:
            config = AppConfig(name="TestApp", options={"arch": arch_str})
            assert processor._parse_architecture(config) == expected_arch

        # Test invalid architecture
        config_invalid = AppConfig(name="TestApp", options={"arch": "invalid-arch"})
        with pytest.raises(ValueError, match="Invalid architecture: invalid-arch"):
            processor._parse_architecture(config_invalid)
