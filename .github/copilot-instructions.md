# GitHub Copilot Instructions

This repository is an automated APK patching system for ReVanced / RVX.
Primary languages: **Bash 4.0+** and **Python 3.13+**.
Full agent guidance: see [`AGENTS.md`](../AGENTS.md).

---

## Essential Commands

```bash
./build.sh config.toml          # Build all enabled apps
./build.sh clean                # Remove temp/, build/, logs/, build.md
./check-env.sh                  # Validate prerequisites
./scripts/lint.sh               # Run all linters (check mode)
./scripts/lint.sh --fix         # Run all linters with auto-fix
bash -n <file.sh>               # Syntax check after editing shell scripts
```

Required env vars: `KEYSTORE_PASSWORD`, `KEYSTORE_ENTRY_PASSWORD`

Python setup: `uv python install 3.14 && uv sync --locked`

---

## Bash Conventions

- Header: `#!/usr/bin/env bash` + `set -euo pipefail`
- Indent: 2 spaces (shfmt enforced)
- Tests: `[[ ... ]]` not `[ ... ]`; quotes: always `"${var}"`
- Command substitution: `$( )` not backticks
- Arrays: `mapfile -t arr < <(cmd)` and `read -ra arr <<< "$str"`
- Globals: `UPPER_SNAKE_CASE`; locals: `lower_snake_case` + `local`
- Public functions: `snake_case`; private: `_leading_underscore`
- **Never** `eval`, unquoted expansions, or pipe curl to shell
- **Always** `source utils.sh` — never source `scripts/lib/*.sh` directly

### Logging

```bash
abort "fatal"      # Red, exits 1
epr "error"        # Red to stderr, continues
log_warn "warn"    # Yellow
log_info "info"    # Cyan (default)
log_debug "debug"  # Gray (LOG_LEVEL=0)
pr "success"       # Green
log "build note"   # Appended to build.md
```

### HTTP Requests

```bash
req "URL" "output"     # Auto-retry (0s/2s/4s/8s/16s backoff)
gh_req "API URL"       # GitHub API with token auth
```

Never call `curl`/`wget` directly — always use `req`.

### Config Access

```bash
source utils.sh
toml_prep "config.toml"
local val=$(toml_get "$table" "key")
local arr=$(toml_get_array_or_string "$table" "patches-source")
```

---

## Python Conventions

- Python 3.13+ (`target-version = "py313"` in pyproject.toml; 3.14 pinned locally)
- Ruff with `select = ["ALL"]`; line length 100; double quotes, 4-space indent
- MyPy `--strict` — all functions need full type annotations
- Docstrings: Google style with `Args:`, `Returns:`, `Raises:`
- Use `selectolax` for HTML, stdlib `tomllib` for TOML, `orjson` for JSON

---

## Module Map

| File | Purpose |
|------|---------|
| `utils.sh` | Module loader — always source this |
| `scripts/lib/logger.sh` | Logging functions |
| `scripts/lib/config.sh` | TOML/JSON config parsing |
| `scripts/lib/network.sh` | HTTP with retry backoff |
| `scripts/lib/cache.sh` | File cache with TTL |
| `scripts/lib/download.sh` | APK sources (APKMirror → Uptodown → Archive.org) |
| `scripts/lib/patching.sh` | APK patching orchestration |
| `scripts/lib/app_processor.sh` | Per-app config + build dispatch |
| `scripts/lib/checks.sh` | Prerequisite validation |
| `scripts/apkmirror_search.py` | APKMirror HTML parser (selectolax) |
| `scripts/toml_get.py` | TOML → JSON converter |

---

## Key Rules

1. `source utils.sh` — never source lib files directly
2. Logging functions only — never raw `echo`/`printf` for messages
3. `./scripts/lint.sh` before every commit
4. `bash -n <file>` after every shell edit
5. `req` for all HTTP — never raw curl/wget
6. Check `cache_is_valid` before downloading
7. No secrets in code — env vars and GitHub secrets only
8. APK signing: v1+v2 only (v3/v4 disabled)
9. Python: type everything, Google docstrings, ruff + mypy clean
10. `jq` for JSON, `toml_get` for TOML, `selectolax` for HTML
