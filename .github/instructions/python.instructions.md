---
applyTo: "**/{*.py,pyproject.toml}"
---

# Python Standards

## Toolchain

- **Lint/Fmt**: `./scripts/lint.sh` or `ruff check --fix && ruff format` (120-char lines)
- **Types**: `mypy --strict` (no `Any`; full annotations)
- **Test**: `uv run python -m pytest tests -v`
- **Deps**: `uv sync --locked --all-groups`

## Core Rules

- **Style**: PEP 8, PEP 257 (Google-style docstrings), PEP 484 (type hints)
- **Line length**: 120 characters (`line-length = 120` in `pyproject.toml`)
- **Types**: Modern generics (`list[str]`); `Protocol` for interfaces; no `Any`
- **Security**: Input validation, no hardcoded secrets, OWASP awareness
- **Perf**: O(n) algorithms; `lru_cache` for expensive ops; generators for large data
- **Arch**: SOLID principles, dependency injection, clean architecture

## Repo-Specific Conventions

- Logging: `from scripts.lib import logging as log` — never use bare `print` in library code
- Network: use `scripts.utils.network` helpers (`req`, `gh_req`, `download_with_lock`)
- HTML parsing: `selectolax`; JSON: `orjson`; TOML reads: `tomllib`
- Config: `scripts.lib.config` for TOML loading; never parse `config.toml` ad-hoc
- Keep `sys.exit()` in `main()` only; return exit codes from helpers
- Test mapping: scrapers → `tests/test_network.py`; APK/signing → `tests/test_apk.py`

## Security Rules

- Never use `eval()` or `exec()` with user input
- Validate all external inputs (APK metadata, scraper responses, TOML values)
- Never hardcode credentials, tokens, or keystore passwords

## Forbidden

- Bare `except:` → catch specific exceptions
- `Any` type → use concrete types or `Protocol`
- Hardcoded secrets → use env vars
- O(n²) loops → use sets/dicts for lookups
- Global mutable state → use DI/parameters

## Import Order

1. Standard library (`os`, `sys`, `pathlib`, `typing`)
2. Third-party (`httpx`, `selectolax`, `orjson`)
3. Local application (`scripts.*`)

## Best Practices

- Use context managers (`with` statements) for file and network resources
- Prefer `pathlib.Path` over `os.path` for file paths
- Use `dataclasses` for plain data containers
