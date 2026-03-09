# AI Agent Instructions

- **Context:** Automated APK patching (ReVanced/RVX) via TOML.
- **Stack:** Bash 4.0+, Python 3.13+, Java 21+, Android SDK 34.0.0, uv, jq.

## Bash
- **Header:** `#!/usr/bin/env bash`, `set -euo pipefail`. 2 spaces indent.
- **Sourcing:** `source utils.sh` ONLY. Never direct `scripts/lib/*.sh`.
- **Variables:** Quote `"${var}"`. `UPPER_SNAKE` globals (`declare -g`/`-gr`). `lower_snake` locals. `_private_func`.
- **Arrays/Dicts:** `mapfile -t arr < <(cmd)`. Access dict keys safely in `set -u` via `"${dict[key]-}"`. No backticks.
- **Execution/Math:** `VAR=$((VAR + 1))` (avoid `((VAR++))` with `set -e`). Single-quote `awk` scripts (`'{print $NF}'`).
- **Errors:** Suffix `grep` with `|| true` if empty is expected.
- **Logging:** `log_info`, `log_warn`, `epr`, `pr`, `abort`. NO raw `echo`/`printf`.
- **Network:** `req "URL" "out"`, `gh_req "API"`. Max retries=4. NO raw `curl`/`wget`.
- **Temp/Cache:** Use deterministic temp paths under `$TEMP_DIR` (see `scripts/lib/network.sh`) with `trap ... RETURN`/`EXIT`. Use `get_cache_path` + `cache_is_valid "$cache_path" <ttl>`.
- **Security:** NO `eval`. Use regex for input validation (prevent path traversal). v1+v2 APK signing only.

## Python
- **Core:** Python 3.13+. Managed via `uv`. Exit codes: 0 (success), 1 (error), 2 (parse/version-check failure).
- **Lint/Type:** Ruff (`select=["ALL"]`), MyPy `--strict`. Google docstrings. 4 spaces.
- **Design:** Keep `sys.exit` in `main()`. Extract core logic for tests. Use walrus operator (`:=`).
- **Parsing:** `selectolax` (HTML), `tomllib` (TOML), `json`/`orjson` (JSON).

## Workflow & Commands
- **Git:** Branch naming: `feature/desc`, `fix/desc`, `agent/desc`. Never commit secrets.
- **Build:** `./build.sh config.toml` (all) | `./build.sh clean` (clean).
- **Lint:** `./scripts/lint.sh` | `./scripts/lint.sh --fix`. (Mandatory pre-commit).
- **Verify:** `bash -n <file.sh>` (Mandatory after edits).
- **Test:** `./tests/test_*.sh` (Bash, no external frameworks) | `uv run python -m pytest tests/<test_file>.py -v` (Python).
- **Deps:** `uv add <pkg>`, then `uv lock` & `uv sync --locked`.
