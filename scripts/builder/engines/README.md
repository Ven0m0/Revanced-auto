# Engine System (apk-tweak integration)

Optional APK processing engines live in this directory. Each engine is a
class with name, stage, and run(ctx: EngineContext) -> EngineResult.

- Pre-patch engines run before ReVanced patching: dtlx, lspatch, rkpairip, whatsapp_patcher.
- Post-patch engines run after patching, before signing: media_optimizer, apk_optimizer, string_cleaner.
- Engines are opt-in via enable-ENGINE = true in config.toml (global default or per-app override).
- Engine-specific options are configured in per-engine sub-tables, e.g. YouTube-Morphed.media-optimizer.
- CLI overrides: --enable-media-optimizer, --disable-media-optimizer, --target-dpi, --optimize-images, etc.
- Plugins can hook pipeline stages by implementing handle_hook(ctx: EngineContext, stage: str) in scripts/plugins/.

## Adding a new engine

1. Create a module in this directory with an Engine class.
2. Register it in __init__.py's _ENGINE_REGISTRY.
3. Add enable_ENGINE fields to GlobalConfig and AppConfig in scripts/builder/config.py.
4. Document options in config.toml.
5. Add tests in tests/test_engines.py or a dedicated test module.
