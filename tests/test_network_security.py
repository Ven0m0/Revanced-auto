"""Tests for security aspects of scripts/utils/network.py."""

# ruff: noqa: S101

from __future__ import annotations

import os
from unittest.mock import patch

from scripts.utils.network import HttpClientConfig


def test_http_client_config_repr_hides_github_token() -> None:
    """Test that HttpClientConfig.__repr__ does not expose the GitHub token."""
    with patch.dict(os.environ, {"GITHUB_TOKEN": "secret_token_12345"}):
        config = HttpClientConfig()
        config_repr = repr(config)
        assert "github_token" not in config_repr
        assert "secret_token_12345" not in config_repr
