#!/usr/bin/env bash
set -euo pipefail

# Emit a GitHub Actions matrix JSON from config.toml.
# Output format: {"include": [{"id": "AppName"}, ...]}
# Only enabled apps (enabled = true, or key absent) are included.
# Optional $1: restrict the matrix to a single app id.

APP_FILTER="${1:-}"

python3 - "$APP_FILTER" <<'PYEOF'
import json
import sys
import tomllib
from pathlib import Path

app_filter = sys.argv[1] if len(sys.argv) > 1 else ""

config_path = Path("config.toml")
if not config_path.exists():
    print('{"include":[]}', end="")
    sys.exit(0)

with config_path.open("rb") as f:
    config = tomllib.load(f)

apps = [
    {"id": key}
    for key, value in config.items()
    if isinstance(value, dict) and value.get("enabled", True) and (not app_filter or key == app_filter)
]

print(json.dumps({"include": apps}), end="")
PYEOF
