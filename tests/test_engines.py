"""Tests for the apk-tweak engine integration."""

# ruff: noqa: S101, TC003, EM101, TRY003

from __future__ import annotations

from pathlib import Path

import pytest

from scripts.builder.config import AppConfig, Config, GlobalConfig
from scripts.builder.engines import (
    EngineContext,
    EngineResult,
    EngineRunner,
    EngineStage,
    create_engine,
    get_available_engines,
    get_engine_stage,
)


class TestEngineRegistry:
    def test_available_engines(self) -> None:
        engines = get_available_engines()
        assert "media_optimizer" in engines
        assert "apk_optimizer" in engines
        assert "string_cleaner" in engines
        assert "dtlx" in engines
        assert "lspatch" in engines
        assert "rkpairip" in engines
        assert "whatsapp_patcher" in engines

    def test_engine_stages(self) -> None:
        assert get_engine_stage("media_optimizer") == EngineStage.POST_PATCH
        assert get_engine_stage("apk_optimizer") == EngineStage.POST_PATCH
        assert get_engine_stage("string_cleaner") == EngineStage.POST_PATCH
        assert get_engine_stage("dtlx") == EngineStage.PRE_PATCH
        assert get_engine_stage("lspatch") == EngineStage.PRE_PATCH

    def test_create_unknown_engine_raises(self) -> None:
        with pytest.raises(ValueError):
            create_engine("nonexistent")


class TestEngineRunner:
    def test_runner_no_engines_returns_apk(self, tmp_path: Path) -> None:
        ctx = EngineContext(
            app_name="Test",
            app_id="com.test",
            version="1.0",
            arch="arm64-v8a",
            current_apk=tmp_path / "input.apk",
            output_dir=tmp_path,
            work_dir=tmp_path / "work",
        )
        runner = EngineRunner(EngineStage.POST_PATCH, [])
        result = runner.run(ctx)
        assert result == ctx.current_apk


class TestEngineConfig:
    def test_global_engine_defaults_disabled(self) -> None:
        cfg = GlobalConfig()
        assert cfg.enable_media_optimizer is False
        assert cfg.enable_apk_optimizer is False
        assert cfg.enable_dtlx is False
        assert cfg.enable_lspatch is False

    def test_global_engine_from_dict(self) -> None:
        cfg = GlobalConfig.from_dict({
            "enable_media_optimizer": True,
            "enable_apk_optimizer": True,
        })
        assert cfg.enable_media_optimizer is True
        assert cfg.enable_apk_optimizer is True

    def test_app_engine_override_inherits_global(self) -> None:
        app = AppConfig.from_dict("Test", {})
        assert app.engine_enabled("media_optimizer", False) is False
        assert app.engine_enabled("media_optimizer", True) is True

    def test_app_engine_override_per_app(self) -> None:
        app = AppConfig.from_dict("Test", {"enable_media_optimizer": True})
        assert app.engine_enabled("media_optimizer", False) is True

    def test_app_lspatch_mode_default(self) -> None:
        app = AppConfig.from_dict("Test", {})
        assert app.lspatch_mode == "complement"

    def test_app_lspatch_mode_alternative(self) -> None:
        app = AppConfig.from_dict("Test", {"lspatch_mode": "alternative"})
        assert app.lspatch_mode == "alternative"

    def test_engine_options_in_options_dict(self) -> None:
        app = AppConfig.from_dict(
            "Test",
            {"media_optimizer": {"optimize_images": True, "target_dpi": "xxhdpi"}},
        )
        assert app.options["media_optimizer"]["optimize_images"] is True
        assert app.options["media_optimizer"]["target_dpi"] == "xxhdpi"
