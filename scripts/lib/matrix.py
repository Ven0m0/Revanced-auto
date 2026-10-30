"""Generate a GitHub Actions build matrix from config.toml. Replaces scripts/generate_matrix.sh."""

from __future__ import annotations

import json
import tomllib
from pathlib import Path
from typing import Any, TypeGuard


def builds_in_ci(app: object) -> TypeGuard[dict[str, Any]]:
    """True for an enabled app table CI can build; a ``stock-apk`` app needs a manually downloaded file."""
    return isinstance(app, dict) and bool(app.get("enabled", True)) and not app.get("stock-apk")


def generate_matrix(config_path: str = "config.toml", app_filter: str = "") -> str:
    """Return the ``{"include": [{"id": ...}, ...]}`` JSON matrix of apps CI can build.

    Only enabled apps (``enabled = true``, or the key absent) without a ``stock-apk`` are included.
    ``app_filter`` restricts the matrix to a single app id, if given.
    """
    path = Path(config_path)
    if not path.exists():
        return json.dumps({"include": []})

    with path.open("rb") as f:
        config = tomllib.load(f)

    apps = [
        {"id": key} for key, value in config.items() if builds_in_ci(value) and (not app_filter or key == app_filter)
    ]
    return json.dumps({"include": apps})
