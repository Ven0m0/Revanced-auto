# GitHub Copilot Instructions

## Project

Automated APK patching system for ReVanced/RVX. Downloads APKs, patches with ReVanced CLI, signs, and outputs to `build/`. Config-driven via TOML.

**Stack:** Python 3.13+, Bash 4.0+, Java 21+, `uv` (package manager), `jq`

---

## Python

### Style
- Python 3.13+. 4-space indent, 120 char line, double quotes, LF endings.
- Ruff with `select = ["ALL"]` (see ignores in `pyproject.toml`). MyPy `--strict`.
- Google-style docstrings. Walrus operator (`:=`) preferred for assignment-in-condition.

### Patterns to follow
```python
# HTTP — use project wrappers, not requests/urllib
from scripts.utils.network import fetch_url

# Logging — use project logger, not print() or stdlib logging at top level
from scripts.lib import logging as log
log.info("message")
log.abort("fatal message", code=1)  # exits

# TOML parsing
import tomllib
with open("config.toml", "rb") as f:
    data = tomllib.load(f)

# HTML parsing
from selectolax.parser import HTMLParser
tree = HTMLParser(html)

# JSON — prefer orjson for performance
import orjson
data = orjson.loads(content)

# Exit codes: 0=success, 1=error, 2=parse/version failure
# Keep sys.exit() only in main()
```

### Structure conventions
- `scripts/builder/` — build orchestration (config, patcher, app_processor, module_gen)
- `scripts/scrapers/` — one file per APK source; extend `base.py`
- `scripts/lib/` — shared utils (config, logging, args, version_tracker)
- `scripts/utils/` — low-level helpers (apk signing, java runner, network, process)
- `tests/` — pytest; extract core logic from `main()` for testability

---

## Bash

### Style
- Shebang: `#!/usr/bin/env bash`. Safety: `set -euo pipefail`. 2-space indent.
- Globals: `UPPER_SNAKE_CASE` (`declare -g` or `declare -gr`). Locals: `lower_snake`. Private functions: `_prefixed`.

### Patterns to follow
```bash
# Source ONLY via utils.sh — never scripts/lib/*.sh directly
source utils.sh

# Quote every variable expansion
echo "${my_var}"
cp "${src}" "${dst}"

# Arrays
mapfile -t items < <(some_command)

# Dict key access under set -u (safe default)
value="${my_dict[key]-}"

# Arithmetic (safe with set -e)
count=$((count + 1))    # good
((count++))             # AVOID — unsafe with set -e

# awk — always single-quote the script
awk '{print $NF}' file

# grep — append || true when empty is OK
grep "pattern" file || true

# Network — use wrappers, never raw curl/wget
req "https://..." "/path/to/output"
gh_req "repos/owner/repo/releases/latest"

# Logging — never raw echo/printf
log_info "Building ${app_name}..."
log_warn "Skipping ${app_name}: no patches"
epr "Download failed for ${url}"
abort "Fatal: missing required tool"
pr "Build complete"         # green success message

# Temp files — use TEMP_DIR with deterministic paths
tmp_file="${TEMP_DIR}/tmp.$(printf '%s' "${key}" | sha256sum | cut -d' ' -f1)"
trap 'rm -f "${tmp_file}"' RETURN

# Cache
cache_path=$(get_cache_path "key")
if ! cache_is_valid "${cache_path}" 86400; then
  # fetch and populate cache
fi
```

### Hard rules
- **No `eval`** — ever.
- **No backticks** — use `$(...)`.
- **No raw `curl`/`wget`** — use `req`/`gh_req`.
- **No raw `echo`/`printf`** — use the logging functions.
- Sign APKs with **v1+v2 only** via `apksigner.jar`.
- Run `bash -n <file.sh>` after every edit.

---

## CLI Entry Points

```bash
# PRIMARY — Python CLI
python -m scripts.cli build [--config config.toml] [--build-mode apk|module|both] [--parallel N] [--clean] [--no-cache]
python -m scripts.cli check
python -m scripts.cli version-tracker {check|save|show|reset}

# LEGACY (deprecated except for cache)
./build.sh [config.toml]
./build.sh cache {stats|cleanup|clean|init}

# Dev workflow
./scripts/lint.sh            # check
./scripts/lint.sh --fix      # auto-fix (run before every commit)
uv run python -m pytest tests/ -v
```

---

## Security

- Never commit `GITHUB_TOKEN`, keystore passwords, or signing keys.
- Validate all external inputs with regex before use (prevent path traversal).
- APK signing: v1+v2 only via `bin/apksigner.jar`.
- Archive extraction must guard against zip slip (see `tests/test_zip_slip.sh`).
