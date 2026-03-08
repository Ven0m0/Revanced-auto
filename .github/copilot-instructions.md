# GitHub Copilot Instructions

Automated APK patching system for ReVanced / RVX. Primary languages: **Bash 4.0+** and **Python 3.13+**. Full agent guidance: [`AGENTS.md`](../AGENTS.md).

## Critical Rules & Tools
- **Module Loader**: `source utils.sh` — never source `scripts/lib/*.sh` directly.
- **Network**: Use `req "URL" "out"` or `gh_req "API"` — **never raw `curl`/`wget`**.
- **Logging**: Use `log_info`, `epr`, `abort` — **never raw `echo`/`printf`**.
- **Caching**: Check `cache_is_valid "key" <ttl>` before downloading.
- **Parsing**: `jq` (JSON), `toml_get` (TOML), `selectolax` (HTML).
- **Secrets**: Use env vars (`KEYSTORE_PASSWORD`) and GitHub secrets — no hardcoded secrets.
- **APK Signing**: v1+v2 only (v3/v4 disabled).
- **Commits**: Run `./scripts/lint.sh` and `bash -n <file.sh>` before committing.
- **Security**: **No `eval`**. No unquoted variables.

## Bash Conventions
- **Header**: `#!/usr/bin/env bash` + `set -euo pipefail`. Indent: 2 spaces.
- **Syntax**: `[[ ... ]]` for tests. `"${var}"` for quoting. `$( )` for command substitution (no backticks).
- **Arrays**: `mapfile -t arr < <(cmd)` and `read -ra arr <<< "$str"`.
- **Variables**: Globals: `UPPER_SNAKE_CASE` | Locals: `lower_snake_case` + `local`.
- **Functions**: Public: `snake_case` | Private: `_leading_underscore`.

## Python Conventions
- **Runtime**: Python 3.13+ (3.14 pinned locally).
- **Typing**: MyPy `--strict` (all functions need full type annotations).
- **Style**: Ruff `select = ["ALL"]`, double quotes, 4-space indent, line length 100.
- **Docstrings**: Google style (`Args:`, `Returns:`, `Raises:`).

## Core Commands
- **Build All**: `./build.sh config.toml`
- **Clean**: `./build.sh clean`
- **Check Env**: `./check-env.sh`
- **Lint (Check)**: `./scripts/lint.sh`
- **Lint (Fix)**: `./scripts/lint.sh --fix`
