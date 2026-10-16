"""Compatibility wrapper around the Python build pipeline."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from scripts.lib.config import Config


class Builder:
    """Backwards-compatible build runner."""

    def __init__(self, config: Config) -> None:
        """Initialize the builder wrapper."""
        self.config = config

    def build_all(self) -> bool:
        """Run the Python build pipeline on the in-memory config and return whether it succeeded."""
        from scripts.builder.app_processor import run

        # Pass the in-memory config so CLI overrides (--parallel, --no-cache) are not lost to a reload.
        return run(self.config.inner) == 0
