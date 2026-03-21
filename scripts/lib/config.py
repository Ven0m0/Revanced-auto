#!/usr/bin/env python3
"""Configuration wrapper module.

Thin wrapper around scripts.builder.config for backwards compatibility.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from scripts.builder.config import (
    AppConfig,
    Config as BuilderConfig,
    ConfigError,
    ConfigLoader,
    GlobalConfig,
    IntegrationSource,
    ModuleConfig,
    load_config as builder_load_config,
)

__all__ = [
    "AppConfig",
    "Config",
    "ConfigError",
    "GlobalConfig",
    "IntegrationSource",
    "ModuleConfig",
]


class Config:
    """Configuration wrapper for APK patching.

    This is a thin wrapper around scripts.builder.config.Config that provides
    a simplified interface with properties for common settings.
    """

    def __init__(self, inner: BuilderConfig, *, use_cache: bool = True) -> None:
        """Initialize Config wrapper.

        Args:
            inner: The underlying builder Config instance.
            use_cache: Whether to use cached downloads (default: True).
        """
        self._inner = inner
        self._use_cache = use_cache

    @classmethod
    def from_file(cls, path: str | Path) -> Config:
        """Load configuration from a TOML file.

        Args:
            path: Path to the TOML configuration file.

        Returns:
            Config instance wrapping the loaded configuration.

        Raises:
            ConfigError: If loading or parsing fails.
        """
        inner = builder_load_config(path)
        return cls(inner)

    @property
    def build_mode(self) -> str:
        """Build mode (apk, module, or both)."""
        return self._inner.global_settings.build_mode

    @build_mode.setter
    def build_mode(self, value: str) -> None:
        """Set build mode."""
        self._inner.global_settings.build_mode = value  # type: ignore[assignment]

    @property
    def parallel_jobs(self) -> int:
        """Number of parallel build jobs."""
        return self._inner.global_settings.parallel_jobs

    @parallel_jobs.setter
    def parallel_jobs(self, value: int) -> None:
        """Set number of parallel jobs."""
        self._inner.global_settings.parallel_jobs = value

    @property
    def use_cache(self) -> bool:
        """Whether to use cached downloads."""
        return self._use_cache

    @use_cache.setter
    def use_cache(self, value: bool) -> None:
        """Set whether to use cached downloads."""
        self._use_cache = value

    @property
    def apps(self) -> dict[str, AppConfig]:
        """Dictionary of app configurations."""
        return self._inner.apps

    def clean(self) -> None:
        """Clean temporary and build directories."""
        temp_dir = Path("temp")
        build_dir = Path("build")
        logs_dir = Path("logs")
        build_md = Path("build.md")

        for path in [temp_dir, build_dir, logs_dir]:
            if path.exists():
                shutil.rmtree(path, ignore_errors=True)

        if build_md.exists():
            build_md.unlink()
