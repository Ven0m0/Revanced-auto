"""Tests for the version-tracking paths of scripts/cli.py."""

# ruff: noqa: S101, TC003

from __future__ import annotations

import argparse
from collections.abc import Iterator
from pathlib import Path

import orjson
import pytest

import scripts.version_tracker as vt_mod
from scripts import cli


@pytest.fixture
def state_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    path = tmp_path / "state.json"
    monkeypatch.setattr(vt_mod, "STATE_FILE", path)
    vt_mod.load_state.cache_clear()  # load_state(None) is cached under the old STATE_FILE
    yield path
    vt_mod.load_state.cache_clear()


@pytest.fixture
def config_path(tmp_path: Path) -> str:
    path = tmp_path / "config.toml"
    path.write_text('cli-version = "5.0.0"\n', encoding="utf-8")
    return str(path)


def _tracker(config_path: str, command: str) -> int:
    return cli.run_version_tracker(argparse.Namespace(config=config_path, version_tracker_command=command))


def test_save_then_reset(config_path: str, state_file: Path) -> None:
    assert _tracker(config_path, "save") == 0
    assert orjson.loads(state_file.read_bytes())["global_cli_version"] == "5.0.0"

    assert _tracker(config_path, "reset") == 0
    assert orjson.loads(state_file.read_bytes()) == {}


def test_check_and_show(config_path: str, state_file: Path) -> None:
    assert _tracker(config_path, "check") == 0
    assert not state_file.exists()
    assert _tracker(config_path, "show") == 0


@pytest.mark.usefixtures("state_file")
def test_build_skips_when_state_matches(config_path: str) -> None:
    _tracker(config_path, "save")
    vt_mod.load_state.cache_clear()
    args = argparse.Namespace(config=config_path, parallel=None, no_cache=False, clean=False)

    assert cli.run_build(args) == 0
    assert vt_mod.check_needs_build(config_path).needs_build is False
