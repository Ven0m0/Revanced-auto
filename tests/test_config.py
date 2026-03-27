"""Tests for scripts/builder/config.py."""

# ruff: noqa: D101, D102, S101, PLR2004, TC003

from __future__ import annotations

from pathlib import Path

import pytest

from scripts.builder.config import AppConfig, ConfigError, ConfigLoader, GlobalConfig, IntegrationSource

# ---------------------------------------------------------------------------
# GlobalConfig
# ---------------------------------------------------------------------------


class TestGlobalConfig:
    def test_default_parallel_jobs(self) -> None:
        assert GlobalConfig().parallel_jobs == 0

    def test_default_build_mode(self) -> None:
        assert GlobalConfig().build_mode == "apk"

    def test_from_dict_ignores_unknown_keys(self) -> None:
        cfg = GlobalConfig.from_dict({"unknown_key": "value", "parallel_jobs": 4})
        assert cfg.parallel_jobs == 4

    def test_from_dict_sets_known_fields(self) -> None:
        cfg = GlobalConfig.from_dict({"riplib": False, "verbose": True})
        assert cfg.riplib is False
        assert cfg.verbose is True


# ---------------------------------------------------------------------------
# AppConfig.from_dict
# ---------------------------------------------------------------------------


class TestAppConfigFromDict:
    def test_basic_creation(self) -> None:
        cfg = AppConfig.from_dict("YouTube", {})
        assert cfg.name == "YouTube"
        assert cfg.enabled is True

    def test_disabled_app(self) -> None:
        cfg = AppConfig.from_dict("YouTube", {"enabled": False})
        assert cfg.enabled is False

    def test_patches_list(self) -> None:
        cfg = AppConfig.from_dict("YouTube", {"patches": ["patch-a", "patch-b"]})
        assert cfg.patches == ["patch-a", "patch-b"]

    def test_exclude_patches(self) -> None:
        cfg = AppConfig.from_dict("YouTube", {"exclude_patches": ["debug-logging"]})
        assert cfg.exclude_patches == ["debug-logging"]

    def test_integrations_builtin(self) -> None:
        cfg = AppConfig.from_dict("YouTube", {"integrations": "built-in"})
        assert cfg.integrations == IntegrationSource.BUILT_IN

    def test_integrations_none(self) -> None:
        cfg = AppConfig.from_dict("YouTube", {"integrations": "none"})
        assert cfg.integrations == IntegrationSource.NONE

    def test_integrations_custom_string(self) -> None:
        cfg = AppConfig.from_dict("YouTube", {"integrations": "my-custom-source"})
        assert cfg.integrations == "my-custom-source"

    def test_remaining_options_in_options_dict(self) -> None:
        cfg = AppConfig.from_dict("YouTube", {"apkmirror_dlurl": "https://example.com"})
        assert cfg.options.get("apkmirror_dlurl") == "https://example.com"

    def test_invalid_name_raises(self) -> None:
        with pytest.raises(ConfigError):
            AppConfig.from_dict("", {})

    def test_invalid_name_type_raises(self) -> None:
        with pytest.raises(ConfigError):
            AppConfig.from_dict(123, {})  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# ConfigLoader
# ---------------------------------------------------------------------------


class TestConfigLoader:
    def test_load_global_config_section(self, tmp_path: Path) -> None:
        """Global settings are parsed from [GlobalConfig] section."""
        cfg_file = tmp_path / "config.toml"
        cfg_file.write_text("[GlobalConfig]\nparallel_jobs = 4\n")
        loader = ConfigLoader()
        config = loader.load(cfg_file)
        assert config.global_settings.parallel_jobs == 4

    def test_load_app_section(self, tmp_path: Path) -> None:
        """App sections are parsed correctly."""
        cfg_file = tmp_path / "config.toml"
        cfg_file.write_text("[YouTube]\nenabled = true\n")
        loader = ConfigLoader()
        config = loader.load(cfg_file)
        assert "YouTube" in config.apps
        assert config.apps["YouTube"].enabled is True

    def test_load_missing_file_raises(self, tmp_path: Path) -> None:
        loader = ConfigLoader()
        with pytest.raises(ConfigError):
            loader.load(tmp_path / "missing.toml")

    def test_load_json_config(self, tmp_path: Path) -> None:
        cfg_file = tmp_path / "config.json"
        cfg_file.write_text('{"YouTube": {"enabled": true}}')
        loader = ConfigLoader()
        config = loader.load(cfg_file)
        assert "YouTube" in config.apps

    def test_env_var_substitution(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("MY_SOURCE", "owner/repo")
        cfg_file = tmp_path / "config.toml"
        cfg_file.write_text('[GlobalConfig]\npatches_source = "ENV:MY_SOURCE"\n')
        loader = ConfigLoader()
        config = loader.load(cfg_file)
        assert config.global_settings.patches_source == "owner/repo"

    def test_multiple_files_later_overrides_earlier(self, tmp_path: Path) -> None:
        first = tmp_path / "a.toml"
        second = tmp_path / "b.toml"
        first.write_text("[GlobalConfig]\nparallel_jobs = 1\n")
        second.write_text("[GlobalConfig]\nparallel_jobs = 8\n")
        loader = ConfigLoader()
        config = loader.load(first, second)
        assert config.global_settings.parallel_jobs == 8

    def test_app_names_returns_enabled_only(self, tmp_path: Path) -> None:
        cfg_file = tmp_path / "config.toml"
        cfg_file.write_text("[YouTube]\nenabled = true\n[Twitter]\nenabled = false\n")
        loader = ConfigLoader()
        config = loader.load(cfg_file)
        assert "YouTube" in config.app_names
        assert "Twitter" not in config.app_names

    def test_defaults_when_no_global_section(self, tmp_path: Path) -> None:
        """With no [GlobalConfig] section, defaults apply."""
        cfg_file = tmp_path / "config.toml"
        cfg_file.write_text("[YouTube]\nenabled = true\n")
        loader = ConfigLoader()
        config = loader.load(cfg_file)
        assert config.global_settings.parallel_jobs == 0
        assert config.global_settings.riplib is True
