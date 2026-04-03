# GitHub Copilot Instructions

Canonical repo guidance lives in `AGENTS.md`. Use this file as the short checklist.

## Repo Focus
ReVanced-auto builds patched APKs from `config.toml`: resolve versions, download stock APKs, patch with ReVanced/RVX-compatible tooling, re-sign, and write outputs to `build/`.

## Prefer These Paths
- New features/fixes: Python first (`scripts/cli.py`, `scripts/lib/`, `scripts/builder/`, `scripts/scrapers/`, `scripts/utils/`)
- Legacy compatibility only: `build.sh`
- Shared Bash loading: `utils.sh` (do not source `scripts/lib/*.sh` directly)

## Working Rules
- Trust current code/config over stale README details.
- Python: 3.13+, `uv` managed, Ruff + MyPy strict, Google-style docstrings.
- Python logging/network/parsing: use `scripts.lib.logging`, existing network helpers, `selectolax`, `tomllib`, `orjson`.
- Bash: `#!/usr/bin/env bash`, `set -euo pipefail`, quote expansions, no `eval`.
- In repo runtime Bash logic, use `req` / `gh_req` and repo logging helpers instead of new raw `curl`/`wget`/user-facing `echo` paths.
- Keep the main build flow intact: config -> version check -> download -> patch -> sign -> output.
- Do not weaken APK signing; keep `bin/apksigner.jar` v1+v2 signing behavior.
- Never commit secrets or edit unrelated files.

## Key Commands
```bash
mise install
uv sync --locked --all-groups
./check-env.sh
python -m scripts.cli build --config config.toml
python -m scripts.cli check --config config.toml
python -m scripts.cli version-tracker {check|save|show|reset} --config config.toml
python -m scripts.cli cache {stats|init|cleanup|clean}
./scripts/lint.sh
uv run python -m pytest tests -v
```

## Test Mapping
- Config / args / version tracking: `tests/test_config.py`, `tests/test_version_tracker.py`
- Network / scrapers: `tests/test_network.py`
- APK / signing: `tests/test_apk.py`
- Notifier: `tests/test_notifier.py`
- After Bash edits: run `bash -n` on changed `.sh` files