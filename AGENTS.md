# AGENTS.md
Guidance for AI coding agents working in this repository. Also linked via `CLAUDE.md` and `GEMINI.md` symlinks.
## Project Overview
Automated APK patching system for ReVanced / RVX. Bash 4.0+ scripts download stock Android APKs and patch them using ReVanced CLI with patch bundles from multiple GitHub sources. Python 3.11+ is used for HTML/TOML parsing utilities.
## Build / Lint / Test Commands
### Building
```bash
./build.sh config.toml          # Build all enabled apps
./build.sh clean                # Remove temp/, build/, logs/, build.md
./check-env.sh                  # Validate prerequisites only
```
Required env vars: `KEYSTORE_PASSWORD`, `KEYSTORE_ENTRY_PASSWORD`. Optional: `KEYSTORE_PATH` (default: `ks.keystore`), `KEYSTORE_ALIAS` (default: `jhc`).
### Linting
```bash
./scripts/lint.sh               # Run ALL linters (check mode)
./scripts/lint.sh --fix         # Run ALL linters with auto-fix
```
Linters run in order: Ruff (Python), MyPy (strict), ShellCheck, shfmt, shellharden, yamllint, yamlfmt, taplo, Biome. Individual linter commands:
```bash
ruff check .                    # Python lint
ruff format --check .           # Python format check
mypy --strict scripts/*.py      # Python type check
shellcheck --color=always *.sh scripts/lib/*.sh  # Shell static analysis
shfmt -d -i 2 -bn -ci -sr *.sh scripts/lib/*.sh # Shell format check
```
### Testing
There is no unified test runner. Run tests individually:
```bash
./tests/test_apkmirror_search.sh   # APKMirror HTML parser (6 cases, standalone)
./tests/test-multi-source.sh       # Multi-source config parsing (7 cases, needs source utils.sh)
./tests/benchmark_download.sh      # Performance benchmarks (standalone)
```
### Syntax Checking
```bash
bash -n build.sh && bash -n utils.sh && bash -n extras.sh && bash -n check-env.sh && bash -n scripts/lib/*.sh
```
## Code Style
### Bash
**Headers** — every script must start with:
```bash
#!/usr/bin/env bash
set -euo pipefail
```
**Indentation**: 2 spaces (shfmt enforced with `-i 2 -bn -ci -sr`).
**Variable naming**:
- Globals / env vars: `UPPER_SNAKE_CASE` (e.g., `TEMP_DIR`, `BUILD_DIR`)
- Constants: `readonly UPPER_SNAKE_CASE` or `declare -r`
- Internal globals: `__DOUBLE_UNDERSCORE__` (e.g., `__TOML__`, `__APKMIRROR_RESP__`)
- Locals: `lower_snake_case`, always declared with `local`
**Function naming**:
- Public: `snake_case` (e.g., `build_rv`, `patch_apk`)
- Private: `_leading_underscore` (e.g., `_determine_version`)
- Validators: `check_*` or `validate_*`
- Getters: `get_*`
**File naming**: `kebab-case.sh` for shell, `snake_case.py` for Python, `UPPERCASE.md` for docs.
**Required patterns**:
- `[[ ... ]]` for tests, never `[ ... ]`
- Always quote expansions: `"${var}"`
- `$( ... )` for command substitution, never backticks
- `command -v tool >/dev/null 2>&1` for existence checks
- `mapfile -t` and `read -ra` for arrays
**Forbidden**:
- `eval` (security risk)
- Unquoted variable expansions
- Piping curl to shell
- Global variable pollution (use `local`)
**Module loading** — always `source utils.sh` to load all libraries. Never source individual `scripts/lib/*.sh` files directly.
### Python
- **Formatter/Linter**: Ruff. Line length 100. Target Python 3.11.
- **Type checking**: MyPy in strict mode (`--strict`). Type hints required on all function signatures.
- **Quote style**: double quotes. **Indent**: 4 spaces.
- **Docstrings**: Google style with `Args:`, `Returns:`, `Raises:` sections for public functions.
- **Ruff rule sets**: `E, W, F, I, N, UP, B, C4, SIM, RUF`.
- **Imports**: sorted by isort via Ruff. First-party: `scripts`.
### Error Handling
```bash
abort "Fatal: reason"              # Red, exits 1
epr "Non-fatal error"             # Red to stderr, continues
log_debug "Detail"                # Gray,   LOG_LEVEL=0
log_info "Info"                   # Cyan,   LOG_LEVEL<=1
log_warn "Warning"                # Yellow, LOG_LEVEL<=2
pr "Success"                      # Green
log "Note for build.md"           # Appends to build.md
```
Set `LOG_LEVEL=0` for debug output. Default is 1 (INFO).
Python scripts use exit code 2 for parse/version-check failures.
### Network Requests
Use `req "URL"` — provides automatic retry with exponential backoff (0s, 2s, 4s, 8s, 16s, then fail). Config: `MAX_RETRIES=4`, `INITIAL_RETRY_DELAY=2`, `CONNECTION_TIMEOUT=10`.
### Config Access
```bash
source utils.sh
toml_prep "config.toml"
local val=$(toml_get "Section" "key")
local arr=$(toml_get_array_or_string "Section" "patches-source")
```
## Architecture
```
utils.sh                    # Module loader (source this, never individual libs)
scripts/lib/
  logger.sh                 # Multi-level logging
  helpers.sh                # Version comparison, HTML parsing wrappers
  config.sh                 # TOML→JSON via Python tomllib
  network.sh                # HTTP with exponential backoff
  cache.sh                  # Build cache with TTL
  prebuilts.sh              # CLI/patches download management
  download.sh               # APK sources: APKMirror → Uptodown → Archive.org
  patching.sh               # APK patching orchestration
  checks.sh                 # Environment prerequisite validation
scripts/*.py                # Python utilities (HTML parsing, TOML, search)
tests/                      # Test scripts + fixtures/
```
**Build pipeline**: Check prerequisites → Parse config.toml → Download CLI + patches → For each app: detect version → download stock APK (fallback chain) → verify signature → patch → optimize → sign → output to `build/`.
**Multi-source patches**: `patches-source` accepts a string or array of GitHub repos. Version detection uses union strategy (highest version supported by at least one source). CLI applies patches via multiple `-p` flags; last patch wins on conflicts.
## Key Rules for Agents
1. Always `source utils.sh` — never source `scripts/lib/*.sh` directly
2. Use logging functions (`log_info`, `epr`, `abort`) — never raw `echo`/`printf` for user messages
3. Run `./scripts/lint.sh` before committing
4. Run `bash -n <file>` after editing any shell script
5. Use `req` for HTTP requests — never raw `curl`/`wget` without retry
6. Cache aggressively — check `is_cached` before downloading
7. Never commit secrets; use env vars and GitHub secrets
8. APK signing is v1+v2 only (v3/v4 disabled)
9. Git branches: `feature/description`, `fix/description`, `claude/description-<session-id>`
10. Prefer `jq` for JSON, Python `tomllib` for TOML, `lxml`+`cssselect` for HTML
