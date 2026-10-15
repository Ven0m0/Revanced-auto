#!/usr/bin/env python3
"""Version tracker wrapper module.

Provides a VersionTracker class that wraps the version tracking logic
from scripts.version_tracker.
"""

from __future__ import annotations

import json
import tomllib
from pathlib import Path
from typing import TYPE_CHECKING

from scripts.version_tracker import (
    CheckResult,
    extract_current_versions,
    load_state,
    save_state,
)

if TYPE_CHECKING:
    from scripts.lib.config import Config

__all__ = ["VersionTracker"]


def _load_raw_config(config_file: str) -> dict[str, object]:
    """Load the source config file as a plain dict (JSON or TOML).

    ``extract_current_versions`` expects a plain mapping (it calls ``.get()``
    and iterates ``.items()``), not the ``scripts.lib.config.Config`` wrapper.
    """
    path = Path(config_file)
    if path.suffix.lower() == ".json":
        loaded: dict[str, object] = json.loads(path.read_text(encoding="utf-8"))
        return loaded
    with path.open("rb") as f:
        return dict(tomllib.load(f))


class VersionTracker:
    """Wraps version tracking logic for smart rebuild detection.

    Attributes:
        config: Configuration object with version information.

    """

    def __init__(self, config: Config) -> None:
        """Initialize the VersionTracker.

        Args:
            config: Configuration object containing version info.

        """
        self._config: Config = config

    def check(self) -> bool:
        """Check if a build is needed based on version changes.

        Returns:
            True if build is needed, False otherwise.

        """
        result = self._get_check_result()
        return result.needs_build

    def save(self) -> None:
        """Save current version state."""
        raw_config = _load_raw_config(self._config.config_file)
        versions = extract_current_versions(raw_config)
        save_state(versions)

    def get_state(self) -> dict[str, str]:
        """Get current state as a dictionary.

        Returns:
            Dictionary of component -> version mappings.

        """
        return dict(load_state())

    def reset(self) -> None:
        """Reset version state."""
        save_state({})

    def _get_check_result(self) -> CheckResult:
        """Get the check result from underlying logic.

        Returns:
            CheckResult with needs_build flag and changes.

        """
        from scripts.version_tracker import detect_changes

        raw_config = _load_raw_config(self._config.config_file)
        current = extract_current_versions(raw_config)
        saved = load_state()

        if not saved:
            return CheckResult(needs_build=True, changes=[])

        changes = detect_changes(current, saved)
        return CheckResult(needs_build=bool(changes), changes=changes)
