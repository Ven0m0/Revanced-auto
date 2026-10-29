"""PostToolUse hook: ruff fix + format on edited Python files."""

import json
import subprocess
import sys

path = json.load(sys.stdin).get("tool_input", {}).get("file_path", "")
if path.endswith(".py"):
    for args in (["check", "--fix", "--quiet"], ["format", "--quiet"]):
        subprocess.run(["uv", "run", "ruff", *args, path], check=False)
