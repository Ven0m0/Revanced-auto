from scripts.lib.config import Config
from pathlib import Path
import pytest

def test_config_wrapper_from_file(tmp_path: Path):
    cfg_file = tmp_path / "config.toml"
    cfg_file.write_text("[GlobalConfig]\nparallel_jobs = 4\n[YouTube]\nenabled = true\n")
    config = Config.from_file(cfg_file)
    assert config.parallel_jobs == 4
    assert "YouTube" in config.apps
    assert config.apps["YouTube"].enabled is True
    assert config.config_file == str(cfg_file)

def test_config_wrapper_properties():
    from scripts.builder.config import Config as BuilderConfig, GlobalConfig
    inner = BuilderConfig(
        global_settings=GlobalConfig(parallel_jobs=2, build_mode="apk"),
        apps={},
        modules={},
        source_files=[],
        loaded_at=None # type: ignore
    )
    config = Config(inner)
    assert config.parallel_jobs == 2
    assert config.build_mode == "apk"

    config.parallel_jobs = 8
    assert inner.global_settings.parallel_jobs == 8

    config.build_mode = "module"
    assert inner.global_settings.build_mode == "module"

def test_config_clean(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "temp").mkdir()
    (tmp_path / "build").mkdir()
    (tmp_path / "logs").mkdir()
    (tmp_path / "build.md").write_text("test")

    from scripts.builder.config import Config as BuilderConfig, GlobalConfig
    inner = BuilderConfig(
        global_settings=GlobalConfig(),
        apps={},
        modules={},
        source_files=[],
        loaded_at=None # type: ignore
    )
    config = Config(inner)
    config.clean()

    assert not (tmp_path / "temp").exists()
    assert not (tmp_path / "build").exists()
    assert not (tmp_path / "logs").exists()
    assert not (tmp_path / "build.md").exists()
