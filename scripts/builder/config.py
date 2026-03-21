#!/usr/bin/env python3
"""Configuration parsing module for APK patching.

Parses TOML/JSON config files and provides typed access to configuration values.
Replaces the legacy scripts/lib/config.sh implementation.

Exit codes:
    0: Success
    1: Error (parsing, validation, or file access failure)
"""

from __future__ import annotations

import importlib.metadata
import json
import os
import sys
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Literal, Union

if sys.version_info < (3, 11):
    import tomllib
else:
    import tomllib


class ConfigError(Exception):
    """Raised when configuration parsing or validation fails."""

    def __init__(self, message: str, *, path: str | None = None) -> None:
        self.path = path
        super().__init__(message)


@dataclass
class GlobalConfig:
    """Global configuration settings applied across all apps."""

    parallel_jobs: int = 0
    build_mode: Literal["apk", "module", "both"] = "apk"
    cli_profile: str = "auto"
    patches_version: str = "latest"
    cli_version: str = "latest"
    patches_source: str | list[str] = "ReVanced/revanced-patches"
    riplib: bool = True
    enable_aapt2_optimize: bool = True
    exclusive_load: bool = False
    merge_manifest: bool = False
    skip_download: bool = False
    version_override: str | None = None
    keystore_path: str | None = None
    keystore_alias: str | None = None
    keystore_password: str | None = None
    key_password: str | None = None
    archive_path: str | None = None
    experimental: bool = False
    verbose: bool = False

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> GlobalConfig:
        """Create GlobalConfig from a dictionary.

        Args:
            data: Dictionary containing global configuration values.

        Returns:
            GlobalConfig instance with values from data dict.
        """
        valid_fields = {f.name for f in cls.__dataclass_fields__.values()}
        filtered = {k: v for k, v in data.items() if k in valid_fields}
        return cls(**filtered)


class IntegrationSource(Enum):
    """Integration source types."""

    BUILT_IN = "built-in"
    CUSTOM = "custom"
    NONE = "none"


@dataclass
class AppConfig:
    """Per-application configuration settings."""

    name: str
    enabled: bool = True
    version: str | None = None
    version_code: int | None = None
    patches_source: str | list[str] | None = None
    patches: list[str] = field(default_factory=list)
    exclude_patches: list[str] = field(default_factory=list)
    merge_patches: list[str] = field(default_factory=list)
    integrations: IntegrationSource | str = IntegrationSource.BUILT_IN
    custom_integrations: str | None = None
    track: bool = True
    exclusive: bool = False
    using: str | None = None
    options: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, name: str, data: dict[str, Any]) -> AppConfig:
        """Create AppConfig from a dictionary.

        Args:
            name: Application name (from TOML section header).
            data: Dictionary containing app-specific configuration values.

        Returns:
            AppConfig instance with values from data dict.
        """
        if not isinstance(name, str) or not name:
            raise ConfigError(f"Invalid app name: {name!r}")

        data = data.copy()
        integrations_raw = data.pop("integrations", "built-in")
        if isinstance(integrations_raw, str):
            try:
                integrations = IntegrationSource(integrations_raw)
            except ValueError:
                integrations = integrations_raw
        else:
            integrations = integrations_raw

        return cls(
            name=name,
            enabled=data.pop("enabled", True),
            version=data.pop("version", None),
            version_code=data.pop("version_code", None),
            patches_source=data.pop("patches_source", None),
            patches=data.pop("patches", []),
            exclude_patches=data.pop("exclude_patches", []),
            merge_patches=data.pop("merge_patches", []),
            integrations=integrations,
            custom_integrations=data.pop("custom_integrations", None),
            track=data.pop("track", True),
            exclusive=data.pop("exclusive", False),
            using=data.pop("using", None),
            options=data,
        )


@dataclass
class ModuleConfig:
    """Module-specific configuration within an app."""

    name: str
    enabled: bool = True
    patches: list[str] = field(default_factory=list)
    exclude_patches: list[str] = field(default_factory=list)
    options: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, name: str, data: dict[str, Any]) -> ModuleConfig:
        """Create ModuleConfig from a dictionary.

        Args:
            name: Module name.
            data: Dictionary containing module configuration values.

        Returns:
            ModuleConfig instance.
        """
        return cls(
            name=name,
            enabled=data.get("enabled", True),
            patches=data.get("patches", []),
            exclude_patches=data.get("exclude_patches", []),
            options=data.get("options", {}),
        )


@dataclass
class Config:
    """Main configuration container holding all parsed settings."""

    global_settings: GlobalConfig
    apps: dict[str, AppConfig]
    modules: dict[str, dict[str, ModuleConfig]]
    source_files: list[Path]
    loaded_at: datetime

    @property
    def app_names(self) -> list[str]:
        """Return list of enabled application names."""
        return [name for name, app in self.apps.items() if app.enabled]

    def get_app(self, name: str) -> AppConfig | None:
        """Get app configuration by name.

        Args:
            name: Application name.

        Returns:
            AppConfig if found and enabled, None otherwise.
        """
        app = self.apps.get(name)
        if app and app.enabled:
            return app
        return None

    def get_module(self, app_name: str, module_name: str) -> ModuleConfig | None:
        """Get module configuration within an app.

        Args:
            app_name: Application name.
            module_name: Module name.

        Returns:
            ModuleConfig if found and enabled, None otherwise.
        """
        app_modules = self.modules.get(app_name, {})
        module = app_modules.get(module_name)
        if module and module.enabled:
            return module
        return None


class ConfigLoader:
    """Loads and parses configuration files (TOML/JSON)."""

    ENV_PATTERN = re.compile(r"ENV:([A-Z_][A-Z0-9_]*)", re.ASCII)
    STRICT_ENV_PATTERN = re.compile(r"\$\{ENV:([A-Z_][A-Z0-9_]*)\}", re.ASCII)

    def __init__(self, *, strict_env: bool = False) -> None:
        """Initialize ConfigLoader.

        Args:
            strict_env: If True, only ${ENV:VAR} syntax is substituted.
                       If False, both ENV:VAR and ${ENV:VAR} are substituted.
        """
        self.strict_env = strict_env

    def load(self, *paths: str | Path) -> Config:
        """Load configuration from one or more files.

        Later files override earlier ones.

        Args:
            *paths: File paths to load (TOML or JSON).

        Returns:
            Parsed Config object.

        Raises:
            ConfigError: If loading or parsing fails.
        """
        source_files: list[Path] = []
        merged_data: dict[str, Any] = {}

        for path in paths:
            path = Path(path).expanduser()
            if not path.exists():
                raise ConfigError(f"Config file not found: {path}", path=str(path))

            try:
                if path.suffix.lower() == ".json":
                    with open(path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                else:
                    with open(path, "rb") as f:
                        data = tomllib.load(f)
            except (OSError, IOError) as e:
                raise ConfigError(f"Failed to read config file: {e}", path=str(path)) from e
            except (ValueError, json.JSONDecodeError) as e:
                raise ConfigError(f"Failed to parse config: {e}", path=str(path)) from e

            source_files.append(path)
            merged_data = self._deep_merge(merged_data, data)

        merged_data = self._substitute_env_vars(merged_data)

        return self._parse(merged_data, source_files)

    def _deep_merge(
        self, base: dict[str, Any], override: dict[str, Any]
    ) -> dict[str, Any]:
        """Merge two dictionaries recursively.

        Args:
            base: Base dictionary.
            override: Override dictionary (takes precedence).

        Returns:
            Merged dictionary.
        """
        result = base.copy()
        for key, value in override.items():
            if (
                key in result
                and isinstance(result[key], dict)
                and isinstance(value, dict)
            ):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = value
        return result

    def _substitute_env_vars(self, data: Any) -> Any:
        """Recursively substitute environment variables in string values.

        Supports both ENV:VAR and ${ENV:VAR} syntax.

        Args:
            data: Data structure to process (dicts, lists, strings, etc.).

        Returns:
            Data with environment variables substituted.
        """
        if isinstance(data, dict):
            return {k: self._substitute_env_vars(v) for k, v in data.items()}
        elif isinstance(data, list):
            return [self._substitute_env_vars(item) for item in data]
        elif isinstance(data, str):
            return self._substitute_string_env(data)
        return data

    def _substitute_string_env(self, value: str) -> str:
        """Substitute environment variables in a string.

        Args:
            value: String that may contain ENV:VAR or ${ENV:VAR} placeholders.

        Returns:
            String with environment variables substituted.
        """
        if self.strict_env:
            pattern = self.STRICT_ENV_PATTERN
        else:
            pattern = re.compile(
                rf"(?:\{)?{re.escape('ENV:')}([A-Z_][A-Z0-9_]*)(?:\})?"
            )

        def replace_env(match: re.Match[str]) -> str:
            var_name = match.group(1)
            return os.environ.get(var_name, match.group(0))

        return pattern.sub(replace_env, value)

    def _parse(
        self, data: dict[str, Any], source_files: list[Path]
    ) -> Config:
        """Parse loaded data into Config dataclass.

        Args:
            data: Merged configuration dictionary.
            source_files: List of source file paths.

        Returns:
            Parsed Config object.

        Raises:
            ConfigError: If validation fails.
        """
        if not isinstance(data, dict):
            raise ConfigError("Config must be a dictionary")

        global_data = data.get("GlobalConfig", {})
        if not isinstance(global_data, dict):
            raise ConfigError("GlobalConfig must be a table/dictionary")

        try:
            global_settings = GlobalConfig.from_dict(global_data)
        except (TypeError, ValueError) as e:
            raise ConfigError(f"Invalid GlobalConfig: {e}") from e

        apps: dict[str, AppConfig] = {}
        modules: dict[str, dict[str, ModuleConfig]] = {}

        for key, value in data.items():
            if key == "GlobalConfig":
                continue

            if not isinstance(value, dict):
                continue

            if "." in key:
                parts = key.split(".", 1)
                app_name, module_name = parts[0], parts[1]
            else:
                app_name, module_name = key, None

            if module_name is None:
                if "module" in value or "integration" in value:
                    modules[app_name] = self._parse_modules(app_name, value)
                else:
                    try:
                        app_config = AppConfig.from_dict(app_name, value)
                        apps[app_name] = app_config
                    except ConfigError:
                        raise
                    except (TypeError, ValueError) as e:
                        raise ConfigError(
                            f"Invalid config for app '{app_name}': {e}"
                        ) from e
            else:
                if app_name not in apps:
                    apps[app_name] = AppConfig(name=app_name)

        return Config(
            global_settings=global_settings,
            apps=apps,
            modules=modules,
            source_files=source_files,
            loaded_at=datetime.now(timezone.utc),
        )

    def _parse_modules(
        self, app_name: str, data: dict[str, Any]
    ) -> dict[str, ModuleConfig]:
        """Parse module configurations for an app.

        Args:
            app_name: Application name.
            data: Configuration dictionary that may contain module keys.

        Returns:
            Dictionary mapping module names to ModuleConfig objects.
        """
        modules: dict[str, ModuleConfig] = {}

        module_data = data.get("module", {})
        if isinstance(module_data, dict):
            for module_name, module_config in module_data.items():
                if isinstance(module_config, dict):
                    try:
                        modules[module_name] = ModuleConfig.from_dict(
                            module_name, module_config
                        )
                    except (TypeError, ValueError):
                        continue

        return modules


def load_config(*paths: str | Path, strict_env: bool = False) -> Config:
    """Load configuration from one or more files.

    Args:
        *paths: File paths to load (TOML or JSON).
        strict_env: If True, only ${ENV:VAR} syntax is substituted.

    Returns:
        Parsed Config object.

    Raises:
        ConfigError: If loading or parsing fails.
    """
    loader = ConfigLoader(strict_env=strict_env)
    return loader.load(*paths)


def get_default_config_path() -> Path | None:
    """Get default config file path if it exists.

    Searches in order:
        1. ./config.toml
        2. ./config.json
        3. ./configs/default.toml
        4. ./configs/default.json

    Returns:
        Path to default config file, or None if not found.
    """
    search_paths = [
        Path("config.toml"),
        Path("config.json"),
        Path("configs/default.toml"),
        Path("configs/default.json"),
    ]

    for path in search_paths:
        if path.exists():
            return path

    return None


def main(argv: list[str]) -> int:
    """Load and validate configuration, printing summary.

    Args:
        argv: Command line arguments (first is program name, second is config path).

    Returns:
        Exit code (0 for success, 1 for error).
    """
    if len(argv) < 2:
        config_path = get_default_config_path()
        if config_path is None:
            print("Usage: config.py <config.toml> [config2.toml ...]", file=sys.stderr)
            print("No default config.toml found", file=sys.stderr)
            return 1
    else:
        config_path = Path(argv[1])

    try:
        config = load_config(config_path)
        print(f"Loaded config from: {config.source_files}")
        print(f"Global settings:")
        print(f"  parallel_jobs: {config.global_settings.parallel_jobs}")
        print(f"  build_mode: {config.global_settings.build_mode}")
        print(f"  patches_source: {config.global_settings.patches_source}")
        print(f"Apps: {config.app_names}")
        for app_name, app in config.apps.items():
            print(f"  {app_name}:")
            print(f"    enabled: {app.enabled}")
            if app.patches_source:
                print(f"    patches_source: {app.patches_source}")
            if app.patches:
                print(f"    patches: {len(app.patches)} patch(es)")
        return 0
    except ConfigError as e:
        print(f"Config error: {e}", file=sys.stderr)
        if e.path:
            print(f"  File: {e.path}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
