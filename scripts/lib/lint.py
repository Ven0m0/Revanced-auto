"""Unified lint runner across Python, YAML, TOML, and JSON/HTML/JS/TS/CSS. Replaces scripts/lint.sh.

Shell linting (ShellCheck/shfmt/shellharden) is dropped along with the shell
scripts it used to check.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING

from scripts.lib import logging as log

if TYPE_CHECKING:
    from collections.abc import Sequence

_EXCLUDED_DIRS = frozenset({".git", "build", "temp", ".venv", "venv", "node_modules", ".omc", ".cache"})


def _find_files(*patterns: str) -> list[str]:
    """Recursively glob patterns from the repo root, skipping build/venv/vcs directories."""
    found: list[str] = []
    for pattern in patterns:
        found.extend(
            str(path) for path in Path().rglob(pattern) if not any(part in _EXCLUDED_DIRS for part in path.parts)
        )
    return sorted(found)


def _run(cmd: Sequence[str]) -> bool:
    """Run a lint command, returning True on success. Missing tool -> warn and skip (True)."""
    if shutil.which(cmd[0]) is None:
        log.warn(f"{cmd[0]} not found, skipping")
        return True
    result = subprocess.run(cmd, check=False)  # noqa: S603
    return result.returncode == 0


def _lint_python(*, fix: bool) -> bool:
    log.info("Python (Ruff)")
    if not _find_files("*.py"):
        log.warn("No Python files found")
        return True
    if fix:
        ok = _run(["ruff", "check", "--fix", "."]) and _run(["ruff", "format", "."])
    else:
        ok = _run(["ruff", "check", "."]) and _run(["ruff", "format", "--check", "."])

    log.info("Python Type Checking (MyPy)")
    # Whole tree, not just scripts/*.py -- the retired lint.sh's glob only ever
    # matched scripts/__init__.py, cli.py, version_tracker.py, silently
    # skipping scripts/builder, scripts/scrapers, scripts/utils, etc.
    return _run(["mypy", "--strict", "scripts"]) and ok


def _lint_yaml(*, fix: bool) -> bool:
    log.info("YAML Files")
    yaml_files = _find_files("*.yml", "*.yaml")
    if not yaml_files:
        log.warn("No YAML files found")
        return True
    ok = _run(["yamllint", *yaml_files])
    return _run(["yamlfmt", "-w", "."]) and ok if fix else _run(["yamlfmt", "-dry", "."]) and ok


def _lint_toml(*, fix: bool) -> bool:
    log.info("TOML Files")
    toml_files = _find_files("*.toml")
    if not toml_files:
        log.warn("No TOML files found")
        return True
    ok = _run(["tombi", "format", *toml_files]) if fix else _run(["tombi", "format", "--check", *toml_files])
    lint_files = [f for f in toml_files if f != "mise.toml"]
    if lint_files:
        ok = _run(["tombi", "lint", *lint_files]) and ok
    else:
        log.warn("No schema-backed TOML files available for tombi lint")
    return ok


def _lint_biome(*, fix: bool) -> bool:
    log.info("JSON/HTML/JS/TS/CSS (Biome)")
    files = _find_files("*.json", "*.html", "*.css", "*.js", "*.ts")
    if not files:
        log.warn("No Biome-managed files found")
        return True
    if fix:
        return _run(["biome", "check", "--write", *files])
    return _run(["biome", "check", *files])


def run_lint(*, fix: bool = False) -> int:
    """Run every lint section and return a process exit code."""
    results = [
        _lint_python(fix=fix),
        _lint_yaml(fix=fix),
        _lint_toml(fix=fix),
        _lint_biome(fix=fix),
    ]
    if all(results):
        log.pr("All linting checks passed!")
        return 0
    log.error("Some linting checks failed")
    if not fix:
        log.pr("Run with --fix to automatically fix issues: python -m scripts.cli lint --fix")
    return 1
