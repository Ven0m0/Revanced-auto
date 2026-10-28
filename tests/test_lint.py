"""Tests for scripts/lib/lint.py's Biome handling (pinned via package.json, run through bunx)."""

# ruff: noqa: S101

from typing import TYPE_CHECKING

from scripts.lib import lint

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path

    import pytest


def _record_runs(monkeypatch: pytest.MonkeyPatch) -> list[list[str]]:
    calls: list[list[str]] = []

    def fake_run(cmd: Sequence[str]) -> bool:
        calls.append(list(cmd))
        return True

    monkeypatch.setattr(lint, "_run", fake_run)
    return calls


def test_ensure_biome_skips_install_when_present(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "node_modules" / "@biomejs" / "biome").mkdir(parents=True)
    calls = _record_runs(monkeypatch)

    assert lint._ensure_biome()
    assert calls == []


def test_ensure_biome_installs_frozen_when_missing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    calls = _record_runs(monkeypatch)

    assert lint._ensure_biome()
    assert calls == [["bun", "install", "--frozen-lockfile"]]


def test_lint_biome_runs_pinned_package_through_bunx(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "node_modules" / "@biomejs" / "biome").mkdir(parents=True)
    (tmp_path / "a.json").write_text("{}")
    calls = _record_runs(monkeypatch)

    assert lint._lint_biome(fix=False)
    assert lint._lint_biome(fix=True)
    assert calls == [
        ["bunx", "--bun", "biome", "check", "a.json"],
        ["bunx", "--bun", "biome", "check", "--write", "a.json"],
    ]
