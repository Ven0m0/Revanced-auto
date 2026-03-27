# AI Agent Instructions

## Project Overview

Automated APK patching system for ReVanced/RVX (ReVanced Extended).
Reads a TOML config, downloads APKs from multiple sources, patches them with ReVanced CLI, signs, and outputs to `build/`.

**Stack:** Python 3.13+, Bash 4.0+, Java 21+, Android SDK 34, `uv`, `jq`

---

## Architecture

```
build.sh              # Entry point (routes to Python CLI; Bash path is deprecated)
utils.sh              # Bash module loader — sources ALL scripts/lib/*.sh
scripts/cli.py        # Python CLI entry point (python -m scripts.cli)
scripts/lib/          # Shared Python + Bash libraries
scripts/builder/      # Build orchestration (app_processor, patcher, config, module_gen)
scripts/scrapers/     # APK download scrapers (APKMirror, APKMonk, APKPure, Uptodown, Aptoide, Archive)
scripts/search/       # Version resolution
scripts/utils/        # APK signing, Java runner, network, process helpers
tests/                # test_*.sh (Bash) + test_*.py (pytest)
config.toml           # App and global build configuration (TOML)
bin/                  # Bundled JARs: apksigner.jar, dexlib2.jar, paccer.jar
```

**Data flow:** `config.toml` → `Config` → `VersionTracker.check()` → scraper download → `Patcher.patch()` → `APKSigner.sign()` → `build/`

---

## Entry Points & Commands

### Python CLI (preferred)
```bash
python -m scripts.cli build [--config config.toml] [--build-mode apk|module|both] [--parallel N] [--clean] [--no-cache]
python -m scripts.cli check [--config config.toml]
python -m scripts.cli version-tracker {check|save|show|reset} [--config config.toml]
```

### Bash (legacy wrapper)
```bash
./build.sh [config.toml]                    # deprecated; routes to Python CLI
./build.sh clean                            # clean build artifacts
./build.sh cache {stats|cleanup|clean|init} # legacy wrapper for Python cache subcommands
```

### Development
```bash
./scripts/lint.sh           # lint all (Python, Shell, YAML, TOML, JSON/HTML)
./scripts/lint.sh --fix     # auto-fix lint issues (mandatory before commit)
bash -n <file.sh>           # syntax-check after every Bash edit
./tests/test_*.sh           # run Bash tests
uv run python -m pytest tests/<file>.py -v  # run Python tests
uv add <pkg> && uv lock && uv sync --locked # add Python dependency
```

---

## Bash Conventions

- **Shebang/safety:** `#!/usr/bin/env bash` + `set -euo pipefail` on every script.
- **Indentation:** 2 spaces. No tabs.
- **Sourcing:** `source utils.sh` only. **Never** `source scripts/lib/*.sh` directly.
- **Variables:** Quote all expansions: `"${var}"`. Globals `UPPER_SNAKE` (`declare -g`/`-gr`). Locals `lower_snake`. Private functions `_prefixed`.
- **Arrays:** `mapfile -t arr < <(cmd)`. Dict key access under `set -u`: `"${dict[key]-}"`. No backticks.
- **Arithmetic:** `VAR=$((VAR + 1))`. Avoid `((VAR++))` — unsafe with `set -e`.
- **awk scripts:** Single-quote: `awk '{print $NF}'`.
- **grep:** Append `|| true` when empty output is acceptable.
- **Logging:** Use `log_info`, `log_warn`, `log_debug`, `epr`, `pr`, `abort`. **No raw `echo`/`printf`.**
- **Network:** `req "URL" "outfile"` or `gh_req "API_PATH"`. Max 4 retries. **No raw `curl`/`wget`.**
- **Temp files:** Use `$TEMP_DIR` with deterministic hashed paths (see `scripts/lib/network.sh`). Clean up with `trap ... RETURN`/`EXIT`.
- **Cache:** `cache_path=$(get_cache_path "key")` then `cache_is_valid "$cache_path" <ttl_seconds>`.
- **Security:** No `eval`. Validate inputs with regex (prevent path traversal). Sign APKs with v1+v2 only.

---

## Python Conventions

- **Version:** Python 3.13+. All dependencies managed via `uv` (`pyproject.toml`).
- **Exit codes:** 0 = success, 1 = runtime error, 2 = parse/version-check failure. Keep `sys.exit` in `main()` only.
- **Linting:** Ruff (`select = ["ALL"]`, ignores in `pyproject.toml`), MyPy `--strict`, Google-style docstrings.
- **Formatting:** 4 spaces, 120 char line limit, double quotes, LF endings.
- **Design:** Extract logic from `main()` for testability. Prefer walrus operator (`:=`) for assignment-in-condition.
- **Parsing:** `selectolax` for HTML, `tomllib` for TOML, `orjson`/`json` for JSON. **No `lxml`/`BeautifulSoup`.**
- **HTTP:** Use `scripts/utils/network.py` wrappers (backed by `httpx`). Never call `requests`/`urllib` directly.
- **Logging:** Use `scripts.lib.logging` (`log.info`, `log.warn`, `log.abort`). Not stdlib `logging` at the top level.

---

## Config Schema (`config.toml`)

Global options (top-level, before any `[Section]`) control defaults for all apps. Each `[AppName]` section can override any global. Required per app: at least one download URL field (`apkmirror-dlurl`, `uptodown-dlurl`, `apkpure-dlurl`, `aptoide-dlurl`, or `archive-dlurl`).

Key globals: `parallel-jobs`, `arch`, `build-mode`, `patches-version`, `cli-version`, `patches-source`, `cli-source`, `riplib`, `compression-level`, `enable-aapt2-optimize`.

---

## Testing

- **Bash:** `./tests/test_*.sh` — no external frameworks; use standard Bash assertions.
- **Python:** `uv run python -m pytest tests/ -v` — uses `pytest`, `pytest-asyncio`, `hypothesis`.
- **Security:** `tests/security_repro_zip_slip.py` / `tests/test_zip_slip.sh` — must pass on all changes touching archive extraction.

---

## Critical Rules

1. **Never** commit secrets (`GITHUB_TOKEN`, keystore passwords, signing keys).
2. **Never** source `scripts/lib/*.sh` directly — always go through `utils.sh`.
3. **Never** use `eval` in Bash.
4. **Never** use raw `curl`/`wget` or `echo`/`printf` for logging — use the wrappers.
5. **Always** run `./scripts/lint.sh` before committing. Fix all errors; warnings from `shellharden` are advisory.
6. **Always** run `bash -n <file.sh>` after any Bash edit.
7. **Always** sign APKs with v1+v2 (`apksigner.jar`). Never skip signing.
8. **Python CLI is primary.** The Bash build path is deprecated and only kept as a wrapper.
9. Branch naming: `feature/desc`, `fix/desc`, `agent/desc`.
