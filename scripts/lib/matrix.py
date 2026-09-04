"""Generate a GitHub Actions build matrix from config.toml. Replaces scripts/generate_matrix.sh."""

from __future__ import annotations

import json
import tomllib
from pathlib import Path


def generate_matrix(config_path: str = "config.toml", app_filter: str = "") -> str:
    """Return the ``{"include": [{"id": ...}, ...]}`` JSON matrix of enabled apps.

    Only enabled apps (``enabled = true``, or the key absent) are included.
    ``app_filter`` restricts the matrix to a single app id, if given.
    """
    path = Path(config_path)
    if not path.exists():
        return json.dumps({"include": []})

    with path.open("rb") as f:
        config = tomllib.load(f)

    apps = [
        {"id": key}
        for key, value in config.items()
        if isinstance(value, dict) and value.get("enabled", True) and (not app_filter or key == app_filter)
    ]
    return json.dumps({"include": apps})
