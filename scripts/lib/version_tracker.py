#!/usr/bin/env python3
"""Version tracker wrapper module.

Provides a VersionTracker class that wraps the version tracking logic
from scripts.version_tracker.
"""

from __future__ import annotations

from scripts.version_tracker import (
    CheckResult,
    extract_current_versions,
    load_state,
    save_state,
)

try:
    from importlib.resources import files
except ImportError:
    pass  # type: ignore[no-redef]

__all__ = ["VersionTracker"]


class VersionTracker:
    """Wraps version tracking logic for smart rebuild detection.

    Attributes:
        config: Configuration object with version information.

    """

    def __init__(self, config: object) -> None:
        """Initialize the VersionTracker.

        Args:
            config: Configuration object containing version info.

        """
        self._config = config

    def check(self) -> bool:
        """Check if a build is needed based on version changes.

        Returns:
            True if build is needed, False otherwise.

        """
        result = self._get_check_result()
        return result.needs_build

    def save(self) -> None:
        """Save current version state."""
        versions = extract_current_versions(self._config)  # type: ignore[arg-type]
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

        current = extract_current_versions(self._config)  # type: ignore[arg-type]
        saved = load_state()

        if not saved:
            return CheckResult(needs_build=True, changes=[])

        changes = detect_changes(current, saved)
        return CheckResult(needs_build=bool(changes), changes=changes)
