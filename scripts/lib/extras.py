"""CI/CD helper commands. Replaces extras.sh."""

from __future__ import annotations

import json
import tomllib
from pathlib import Path

from scripts.lib import logging as log


def separate_config(input_config: str, app_name: str, output_config: str) -> None:
    """Extract one app's table plus the top-level defaults into its own config file.

    Writes JSON regardless of ``output_config``'s extension -- scripts/builder/config.py
    loads both .toml and .json, and JSON is trivial to emit without a TOML writer.
    """
    log.info(f"Separating config for: {app_name}")
    input_path = Path(input_config)
    if not input_path.exists():
        log.abort(f"Config file not found: {input_config}")

    with input_path.open("rb") as f:
        config = tomllib.load(f)

    if app_name not in config or not isinstance(config[app_name], dict):
        log.abort(f"App '{app_name}' not found in config")

    main_config = {k: v for k, v in config.items() if not isinstance(v, dict)}
    new_config = {**main_config, app_name: config[app_name]}

    Path(output_config).write_text(json.dumps(new_config), encoding="utf-8")
    log.info(f"Separated config saved to: {output_config}")


_GMSCORE_NOTE = """### MicroG / GmsCore (Required for YouTube & YT Music)
Download and install [MicroG-RE](https://github.com/morpheapp/microg-RE/releases/latest).
"""


def combine_logs(logs_dir: str) -> str:
    """Concatenate every build.md found under logs_dir, separated by '---', then the GmsCore note once."""
    # No stdout logging here: the caller prints this function's result into the GitHub release body.
    dir_path = Path(logs_dir)
    if not dir_path.is_dir():
        log.warn(f"Logs directory not found: {logs_dir} (no build-log-* artifacts uploaded)")
        return "No builds completed"

    log_files = sorted(dir_path.rglob("build.md"))
    if not log_files:
        log.warn(f"No build.md files found in {logs_dir}")
        return "No builds completed"

    logs = "\n\n---\n\n".join(f.read_text(encoding="utf-8") for f in log_files)
    return f"{logs}\n\n---\n\n{_GMSCORE_NOTE}"
