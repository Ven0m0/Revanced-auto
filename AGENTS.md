# AGENTS.md

Guidance for AI coding agents working in this repository.
Also linked via `CLAUDE.md` and `GEMINI.md` symlinks, and mirrored in `.github/copilot-instructions.md`.

---

## Key Rules for Agents

1. **Always `source utils.sh`** — never source `scripts/lib/*.sh` files directly.
2. **Use logging functions** (`log_info`, `epr`, `abort`) — never raw `echo`/`printf` for user-visible messages.
3. **Run `./scripts/lint.sh`** before committing any change.
4. **Run `bash -n <file>`** immediately after editing any shell script.
5. **Use `req` for HTTP** — never raw `curl`/`wget` without the retry wrapper.
6. **Cache aggressively** — call `cache_is_valid` before downloading anything.
7. **Never commit secrets** — use env vars and GitHub secrets.
8. **APK signing is v1+v2 only** — v3/v4 are disabled by design.
9. **Git branch naming**: `feature/description`, `fix/description`, `claude/description-<session-id>`.
10. **Prefer `jq`** for JSON, `toml_get` / Python `tomllib` for TOML, `selectolax` for HTML.
11. **Python version is 3.13+** (3.14 pinned locally) — do not use 3.11/3.12 APIs/syntax.
12. **Type everything** — all Python function signatures must have full type annotations.
13. **`eval` is banned** — find another approach.
14. **Multi-source patches**: `patches-source` can be a string or `["repo1", "repo2"]` array; version detection uses union strategy (highest version supported by ≥1 source).

---

## Project Context

**One-line description**: Automated APK patching system that downloads stock Android APKs and patches them with ReVanced / RVX using a TOML-driven configuration.
**Core Stack**: Bash 4.0+ (build orchestration), Python 3.13+ (HTML/TOML utilities), Java 21+, Android SDK build-tools 34.0.0, standard POSIX utilities (`jq`, `zip`, `curl`).
**Package manager**: `uv` (Python). No Node.js.

---

## Conventions & Style

### Bash Scripts
- **Header**: `#!/usr/bin/env bash` and `set -euo pipefail`.
- **Naming**: `UPPER_SNAKE_CASE` (globals/env vars), `readonly UPPER_SNAKE_CASE` (constants), `__DOUBLE_UNDERSCORE__` (internal globals), `lower_snake_case` (locals/functions), `_leading_underscore` (private functions).
- **Patterns**: `[[ -n "$var" ]]`, always quote expansions `"${var}"`, use `$()` not backticks, use `mapfile -t` and `read -ra` for arrays.
- **Forbidden**: `eval`, unquoted variables, backticks, `curl | bash`, global variable pollution (use `local` in functions), direct sourcing of `scripts/lib/*.sh`.
- **Module loading**: `source utils.sh`
- **Error Handling**: `abort "fatal"` (red/exit 1), `epr "err"` (red/continue), `log_info "info"` (cyan), `log_debug "debug"` (LOG_LEVEL=0), `log_warn "warn"` (yellow), `pr "success"` (green), `log "note"` (appends to build.md).
- **Network**: `req "URL" "out"` (auto-retries), `gh_req "API_URL"`, `gh_dl "RELEASE_URL"`. Max retries=4.
- **Config**: Parsed via `toml_get.py` into `__TOML__`. Access via `toml_get` or `toml_get_array_or_string`.
- **Caching**: `cache_is_valid "key" <ttl_seconds>` then `get_cache_path` else `cache_put`. Located in `temp/.cache/`.

### Python Scripts
- **Runtime**: Python 3.13+ (3.14 pinned in `.python-version`).
- **Formatter**: Ruff (`ruff format`): double quotes, LF, 4-space indent.
- **Linter**: Ruff with `select = ["ALL"]` (see `pyproject.toml` for ignores like `E501`, `T201`).
- **Types**: MyPy `--strict`.
- **Docstrings**: Google style (`Args:`, `Returns:`, `Raises:`).
- **Imports**: isort via Ruff. Namespace: `scripts`.
- **Exit codes**: 0 (success), 1 (error), 2 (parse/version-check failure).

### File Naming
- Shell: `kebab-case.sh` | Python: `snake_case.py` | Docs: `UPPERCASE.md` | Test Configs: `*-test.toml`.

---

## Common Tasks & Actions

- **Build all enabled apps**: `./build.sh config.toml`
- **Build single app**: `./extras.sh separate-config config.toml AppName sep.toml && ./build.sh sep.toml`
- **Clean build directory**: `./build.sh clean`
- **Check prerequisites**: `./check-env.sh`
- **Lint all files (check)**: `./scripts/lint.sh`
- **Lint all files (fix)**: `./scripts/lint.sh --fix`
- **Python-specific lint**: `uv run ruff check . && uv run ruff format --check . && uv run mypy --strict scripts/*.py`
- **Shell-specific lint**: `shellcheck --color=always $(find . -name "*.sh" ! -path "./.git/*")` and `shfmt -d -i 2 -bn -ci -sr <file.sh>`
- **Run Python tests**: `uv run python -m pytest tests/<test_file>.py -v`
- **Run Shell tests**: `./tests/<test_script>.sh`
- **Update Python deps**: `uv add <pkg>` (or `--dev`), then `uv lock` and `uv sync --locked`. Commit `pyproject.toml` and `uv.lock`.
- **Verify Bash syntax**: `bash -n <script.sh>`

---

## Tooling & Dependencies

- **Python Runtime Packages**: `selectolax` (HTML parsing), `requests`/`httpx[http2]` (HTTP), `orjson` (fast JSON), `asyncpraw`/`uvloop`/`aiofiles` (async tools).
- **Python Dev Packages**: `ruff` (lint/format), `mypy` (typing).
- **System Tools**: `java` (21+), Android SDK `build-tools` (34.0.0 for `aapt2`, `zipalign`, `apksigner`), `jq` (JSON processing), `zip`/`unzip` (APK packaging), `curl` (HTTP), `uv` (Python pkg manager).
- **CI Linters**: ShellCheck (0.10.0), shfmt (3.10.0), shellharden (4.3.1), yamllint, yamlfmt (0.14.0), taplo (0.9.3, TOML), Biome (2.3.11, JSON/HTML/JS/CSS).

## CI/CD Overview
- **PRs**: Syntax validation (`bash -n`), tests (`test-multi-source.sh`), test build (no signing), bot summary.
- **Push/PR Linters**: Ruff, ShellCheck, shfmt, shellharden, yamllint, yamlfmt, taplo, Biome (all `continue-on-error: true`).
- **Main/Master**: Daily build check (06:00 UTC) triggers parallel matrix builds (`generate_matrix.sh`), combines logs, and publishes GitHub Releases.
- **Dependency Checks**: Daily (00:00 UTC) checks for ReVanced CLI, patches, and APKs.
