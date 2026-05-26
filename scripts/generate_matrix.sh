#!/usr/bin/env bash
set -euo pipefail

# Emit a GitHub Actions matrix JSON from config.toml.
# Output format: {"include": [{"id": "AppName"}, ...]}
# Only enabled apps (enabled = true, or key absent) are included.

python3 - <<'PYEOF'
import json
import sys
import tomllib
from pathlib import Path

config_path = Path("config.toml")
if not config_path.exists():
    print('{"include":[]}', end="")
    sys.exit(0)

with config_path.open("rb") as f:
    config = tomllib.load(f)

apps = [
    {"id": key}
    for key, value in config.items()
    if isinstance(value, dict) and value.get("enabled", True)
]

print(json.dumps({"include": apps}), end="")
PYEOF
