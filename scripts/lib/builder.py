"""Compatibility wrapper for invoking the legacy build shell script."""

import subprocess

from scripts.lib.config import Config


class Builder:
    """Backwards-compatible build runner."""

    def __init__(self, config: Config) -> None:
        """Initialize the builder wrapper."""
        self.config = config

    def build_all(self) -> bool:
        """Run the new Python build pipeline and return whether it succeeded."""
        from scripts.builder.app_processor import main

        return main(["app_processor.py", self.config.config_file]) == 0
