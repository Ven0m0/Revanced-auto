"""PreToolUse hook: block edits to CI state, secrets, keystores and lock files."""

import json
import re
import sys

BLOCKED = re.compile(
    r"(^|/)(\.github/last_built_versions\.json|uv\.lock|\.env[^/]*|[^/]+\.(keystore|jks|bks|p12|pem))$"
)

path = json.load(sys.stdin).get("tool_input", {}).get("file_path", "").replace("\\", "/")
if BLOCKED.search(path):
    print(f"Blocked: {path} is generated state, a lock file or a secret (see CLAUDE.md Safety).", file=sys.stderr)
    sys.exit(2)
