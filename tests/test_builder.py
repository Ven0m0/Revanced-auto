"""Tests for the Builder wrapper class."""

# ruff: noqa: S101

import argparse
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

from scripts.builder.config import Config as BuilderConfig
from scripts.builder.config import GlobalConfig
from scripts.lib.args import build_parser
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


@patch("scripts.builder.app_processor.run")
def test_builder_build_all_success(mock_run: MagicMock) -> None:
    """Test build_all returns True when the app processor exits 0."""
    mock_config = _mock_config()
    mock_run.return_value = 0
    builder = Builder(mock_config)

    result = builder.build_all()

    assert result is True
    mock_run.assert_called_once_with(mock_config.inner)


@patch("scripts.builder.app_processor.run")
def test_builder_build_all_failure(mock_run: MagicMock) -> None:
    """Test build_all returns False when the app processor exits non-zero."""
    mock_run.return_value = 1
    builder = Builder(_mock_config())

    assert builder.build_all() is False


@patch("scripts.builder.app_processor.run", return_value=0)
def test_build_all_passes_in_memory_overrides(mock_run: MagicMock) -> None:
    """CLI overrides (--parallel, --no-cache) must reach the pipeline instead of being lost to a reload."""
    inner = BuilderConfig(
        global_settings=GlobalConfig(parallel_jobs=1),
        apps={},
        modules={},
        source_files=[],
        loaded_at=datetime.now(UTC),
    )
    config = Config(inner)
    config.parallel_jobs = 4
    config.use_cache = False

    Builder(config).build_all()

    passed = mock_run.call_args.args[0]
    assert passed is inner
    assert passed.global_settings.parallel_jobs == 4
    assert passed.global_settings.use_cache is False


def test_build_parallel_defaults_to_none() -> None:
    """Without --parallel the config's parallel-jobs must win, so the parser default is None."""
    parser = argparse.ArgumentParser()
    build_parser(parser.add_subparsers(dest="command"))

    args = parser.parse_args(["build"])

    assert args.parallel is None
    assert not hasattr(args, "build_mode")
