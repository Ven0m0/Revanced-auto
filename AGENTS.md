# ReVanced-auto Agent Guide (Canonical)

This is the canonical instruction file for AI agents in this repository.

## Source of Truth
- Keep `.github/copilot-instructions.md` aligned, but shorter.
- If documentation disagrees, trust current behavior in `scripts/`, `pyproject.toml`, `mise.toml`, and active workflows.

## Repository Goal
Automate the end-to-end ReVanced build pipeline from TOML config: resolve compatible app versions, download stock APKs, patch with ReVanced/RVX-compatible tooling, re-sign, and write artifacts to `build/`.

## Preferred Entry Points
```bash
mise install
uv sync --locked --all-groups
python -m scripts.cli check-env
python -m scripts.cli build --config config.toml --build-mode apk|module|both --parallel N --clean --no-cache
python -m scripts.cli check --config config.toml
python -m scripts.cli version-tracker {check|save|show|reset} --config config.toml
python -m scripts.cli cache {stats|init|cleanup|clean}
python -m scripts.cli matrix [--config config.toml] [app_filter]
python -m scripts.cli extras {separate-config|combine-logs} ...
python -m scripts.cli lint [--fix]
uv run python -m pytest tests -v
```

## High-Value Paths
| Path | Purpose |
| --- | --- |
| `scripts/cli.py` | Primary CLI entry point |
| `scripts/lib/args.py` | CLI argument model |
| `scripts/lib/config.py` | Compatibility wrapper around canonical config logic |
| `scripts/lib/version_tracker.py` | Version state tracking |
| `scripts/lib/builder.py` | Build orchestration |
| `scripts/lib/env_check.py` | Environment/prerequisite checks (`check-env` subcommand) |
| `scripts/lib/extras.py` | CI/CD helpers: separate-config, combine-logs |
| `scripts/lib/matrix.py` | GitHub Actions build matrix generation |
| `scripts/lib/lint.py` | Unified lint runner (ruff, mypy, yamllint, tombi, biome) |
| `scripts/builder/` | Build pipeline components |
| `scripts/lib/plugins.py` | Auto-discovered plugin hook dispatcher |
| `scripts/plugins/` | User plugin directory |
| `scripts/scrapers/` | Source-specific APK retrieval |
| `scripts/search/` | Version resolution |
| `scripts/utils/` | Shared APK, Java, process, network, and keystore helpers |
| `config.toml` | Global + per-app configuration |
| `tests/` | Pytest suite |

## Change Priorities
- All entry points are Python (`scripts/cli.py`); no shell pipeline remains.
- Keep edits localized to the owning module/directory.
- Reuse existing helpers and wrappers before adding new abstractions.
- Keep refactors scoped to what the task requires; broad refactors need explicit user request.

## Language & Tooling Rules

### Python
- Target Python 3.13 or newer; dependencies are `uv`-managed.
- Match repository tooling: Ruff (`line-length=120`, `select=["ALL"]` with repo-specific ignores) and MyPy strict mode.
- Use `from scripts.lib import logging as log` for logging.
- Reuse existing network helpers (`scripts/utils/network.py`); avoid ad-hoc new HTTP stacks.
- Prefer `selectolax` for HTML, `tomllib` for TOML reads, and `orjson`/`json` for JSON.
- Keep sys.exit in `main()` only; return status codes from helpers.
- Favor testable functions over growing `main()` flow logic.

### GitHub Actions
- Use explicit release tags for `uses:` instead of SHA pinning in this repository.

## Domain Invariants
- `config.toml` uses top-level defaults plus per-app override sections.
- Every enabled app must define at least one supported download source.
- Preserve the core flow: config -> version check -> download -> patch -> sign -> output.
- Keep signing hardening intact: output APKs must be re-signed via apksigner.jar with v1+v2 only. Keystores are converted to BKS via `scripts/utils/keystore.py::ensure_bks` before patching, since Morphe's patcher only accepts BKS.
- Treat cached/network/archive handling changes as high risk and validate carefully.

## Validation Matrix
- Python changes: `uv run python -m scripts.cli lint` and relevant pytest targets.
- Config / args / version tracking: `uv run python -m pytest tests/test_config.py tests/test_version_tracker.py -v`
- Network / scraper logic: `uv run python -m pytest tests/test_network.py -v`
- APK / signing logic: `uv run python -m pytest tests/test_apk.py tests/test_keystore.py -v`
- Notifier logic: `uv run python -m pytest tests/test_notifier.py -v`
- Broad Python changes: `uv run python -m pytest tests -v`

## Safety
- Keep secrets (`GITHUB_TOKEN`, signing credentials, private keys, passwords) out of commits; use env vars or GitHub secrets instead.
- Leave CI-generated version-tracking state under `.github/` untouched unless the task explicitly requires editing it.
- Keep changes scoped and minimal; avoid unrelated cleanup.
