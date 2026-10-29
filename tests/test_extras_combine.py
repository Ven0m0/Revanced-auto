"""Tests for scripts.lib.extras.combine_logs."""

# ruff: noqa: S101

from __future__ import annotations

from typing import TYPE_CHECKING

from scripts.lib.extras import combine_logs

if TYPE_CHECKING:
    from pathlib import Path


def test_gmscore_note_appended_once(tmp_path: Path) -> None:
    for name in ("a", "b"):
        (tmp_path / name).mkdir()
        (tmp_path / name / "build.md").write_text(f"### {name}\n", encoding="utf-8")

    combined = combine_logs(str(tmp_path))

    assert combined.count("MicroG / GmsCore") == 1
    assert combined.rstrip().endswith("(https://github.com/morpheapp/microg-RE/releases/latest).")
    assert "ReVanced/GmsCore" not in combined
