# ReVanced-auto AI Instructions

## Scope
- This is the canonical instruction file for AI agents working in this repo.
- Keep `.github/copilot-instructions.md` aligned but shorter.
- When docs disagree, trust current code in `scripts/`, `pyproject.toml`, `mise.toml`, and workflows over older README prose.

## Repo Purpose
ReVanced-auto automates downloading stock APKs, resolving compatible versions, patching them with ReVanced/RVX-compatible CLI + patches, re-signing outputs, and writing artifacts to `build/` from a TOML config.

## Prefer These Entry Points
```bash
mise install
uv sync --locked --all-groups
./check-env.sh
python -m scripts.cli build --config config.toml --build-mode apk|module|both --parallel N --clean --no-cache
python -m scripts.cli check --config config.toml
python -m scripts.cli version-tracker {check|save|show|reset} --config config.toml
python -m scripts.cli cache {stats|init|cleanup|clean}
./build.sh ...   # legacy wrapper; keep compatible, but prefer Python CLI
./scripts/lint.sh
./scripts/lint.sh --fix
uv run python -m pytest tests -v
```

## Repo Map
| Path | Use |
| --- | --- |
| `scripts/cli.py` | Main CLI entry point |
| `scripts/lib/args.py` | CLI argument definitions |
| `scripts/lib/config.py` | TOML config loading and normalization |
| `scripts/lib/version_tracker.py` | Update detection and saved state |
| `scripts/lib/builder.py` | Build orchestration |
| `scripts/builder/` | Higher-level build pipeline pieces |
| `scripts/scrapers/` | APK source-specific download logic |
| `scripts/search/` | Version resolution |
| `scripts/utils/` | APK, Java, process, and network helpers |
| `build.sh` | Compatibility wrapper around the Python CLI |
| `utils.sh` | Bash loader for shared shell modules |
| `config.toml` | Global defaults + per-app overrides |
| `tests/` | Pytest suite |

## Change Strategy
- Prefer extending the Python path for new behavior; the Bash build path is mostly compatibility glue.
- Keep changes localized: scraper work in `scripts/scrapers/`, config work in `scripts/lib/config.py`, build flow in `scripts/lib/builder.py` or `scripts/builder/`.
- Reuse existing wrappers before adding new helpers.
- Avoid broad refactors unless the task requires them.

## Python Rules
- Target Python 3.13+ and existing deps managed by `uv`.
- Match repo tooling: Ruff (`line-length = 120`, `select = ["ALL"]` with repo ignores), MyPy `--strict`, Google-style docstrings.
- Use `from scripts.lib import logging as log` for CLI/lib logging.
- Use `scripts.utils.network` / existing network helpers; do not introduce `requests` or ad-hoc `urllib` calls.
- Prefer `selectolax` for HTML parsing, `tomllib` for TOML reads, and `orjson`/`json` for JSON.
- For GitHub Actions, use explicit release tags instead of SHA-pinned `uses:` references.
- Keep `sys.exit()` in `main()` only; return exit codes from helpers.
- Add logic to testable functions instead of growing `main()` bodies.

## Bash Rules
- Use `#!/usr/bin/env bash` and `set -euo pipefail`.
- Source shared shell code via `source utils.sh`; do not source `scripts/lib/*.sh` directly.
- In build/runtime shell code, use repo logging helpers (`log_info`, `log_warn`, `log_debug`, `pr`, `epr`, `abort`) instead of adding new raw user-facing `echo`/`printf` paths.
- Use `req` / `gh_req` for network access instead of raw `curl`/`wget` in repo runtime logic.
- Quote expansions, prefer `mapfile -t`, use `VAR=$((VAR + 1))`, and never use `eval`.
- Run `bash -n` on every changed shell file.

## Domain Invariants
- `config.toml` uses top-level globals plus per-app `[Section]` overrides.
- Each enabled app needs at least one supported download source field.
- Preserve the normal flow: config load -> version check -> download -> patch -> sign -> output.
- Do not weaken signing behavior: built APKs must be re-signed with `bin/apksigner.jar` using v1+v2 only.
- Keep `build.sh` behavior aligned with `scripts.cli`; do not add new primary features only to the legacy wrapper.
- Be careful with cached/networked paths and external archive handling.

## Validation Matrix
- Any Python change: run `./scripts/lint.sh` and the most relevant pytest targets.
- Config / CLI args / version tracking: `uv run python -m pytest tests/test_config.py tests/test_version_tracker.py -v`
- Network / scraper changes: `uv run python -m pytest tests/test_network.py -v`
- APK / signing changes: `uv run python -m pytest tests/test_apk.py -v`
- Notifier changes: `uv run python -m pytest tests/test_notifier.py -v`
- Broad Python changes: `uv run python -m pytest tests -v`
- Any Bash change: `bash -n path/to/file.sh` plus `./scripts/lint.sh`

## Safety
- Never commit secrets such as `GITHUB_TOKEN`, keystore passwords, or private signing material.
- Do not edit generated/stateful files such as `.github/last_built_versions.json` unless the task explicitly requires it.
- Keep changes repo-specific and minimal; do not rewrite unrelated docs or workflow files for incidental cleanup.
