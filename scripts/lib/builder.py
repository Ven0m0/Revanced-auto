"""Compatibility wrapper for invoking the legacy build shell script."""

import subprocess

from scripts.lib.config import Config


class Builder:
    """Backwards-compatible build runner."""

    def __init__(self, config: Config) -> None:
        """Initialize the builder wrapper."""
        self.config = config

    def build_all(self) -> bool:
        """Run the legacy build entry point and return whether it succeeded."""
        result = subprocess.run(  # noqa: S603
            ["./build.sh", self.config.config_file],
            capture_output=True,
            check=False,
            text=True,
        )
        return result.returncode == 0
