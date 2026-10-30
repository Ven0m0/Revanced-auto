"""Tests for scripts/lib/matrix.py."""

# ruff: noqa: S101

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from scripts.lib.matrix import generate_matrix

if TYPE_CHECKING:
    from pathlib import Path


def test_matrix_skips_disabled_and_local_stock_apk_apps(tmp_path: Path) -> None:
    config = tmp_path / "config.toml"
    config.write_text(
        'patches-source = "x"\n[A]\n[B]\nenabled = false\n[Discord]\nstock-apk = "stock/discord.apkm"\n',
        encoding="utf-8",
    )

    assert json.loads(generate_matrix(str(config))) == {"include": [{"id": "A"}]}
    assert json.loads(generate_matrix(str(config), "Discord")) == {"include": []}
