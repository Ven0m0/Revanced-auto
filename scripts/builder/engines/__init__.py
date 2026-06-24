"""Engine base module for APK modification pipeline.

Defines the engine protocol, runtime context, result type, and registry
used by all optional APK processing engines ported from apk-tweak.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    from collections.abc import Callable


class EngineStage(Enum):
    """Pipeline stage at which an engine executes."""

    PRE_PATCH = "pre_patch"
    POST_PATCH = "post_patch"


@dataclass
class EngineContext:
    """Runtime context passed to every engine.

    Attributes:
        app_name: Display name of the app being built.
        app_id: Package ID / config section name.
        version: App version being processed.
        arch: Target architecture.
        current_apk: Path to the APK at the current pipeline stage.
        output_dir: Directory for final output files.
        work_dir: Temporary working directory for intermediate files.
        global_options: Global engine options from config.
        app_options: Per-app engine options from config.
        metadata: Dict for storing engine results.
    """

    app_name: str
    app_id: str
    version: str
    arch: str
    current_apk: Path
    output_dir: Path
    work_dir: Path
    global_options: dict[str, Any] = field(default_factory=dict)
    app_options: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def log(self, message: str, *, level: int = 20) -> None:
        """Log a message using the repo logging helpers.

        Args:
            message: Message to log.
            level: Logging level (default: INFO).
        """
        from scripts.lib import logging as log

        formatted = f"[{self.app_name}] {message}"
        if level >= 40:
            log.error(formatted)
        elif level >= 30:
            log.warn(formatted)
        elif level >= 20:
            log.info(formatted)
        else:
            log.debug(formatted)


@dataclass
class EngineResult:
    """Result of an engine execution.

    Attributes:
        success: Whether the engine completed successfully.
        output_apk: Path to the modified APK, or None if not modified.
        metadata: Arbitrary metadata produced by the engine.
        error: Error message if the engine failed.
    """

    success: bool
    output_apk: Path | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


class Engine(Protocol):
    """Protocol for APK modification engines."""

    name: str
    stage: EngineStage

    def run(self, ctx: EngineContext) -> EngineResult:
        """Execute the engine.

        Args:
            ctx: Runtime engine context.

        Returns:
            EngineResult describing the outcome.
        """
        ...


from scripts.lib import logging as log
from scripts.lib.plugins import dispatch_plugins


# Engine name -> (module_path, class_name, stage)
_ENGINE_REGISTRY: dict[str, tuple[str, str, EngineStage]] = {
    "media_optimizer": ("scripts.builder.engines.media_optimizer", "MediaOptimizerEngine", EngineStage.POST_PATCH),
    "apk_optimizer": ("scripts.builder.engines.apk_optimizer", "APKOptimizerEngine", EngineStage.POST_PATCH),
    "string_cleaner": ("scripts.builder.engines.string_cleaner", "StringCleanerEngine", EngineStage.POST_PATCH),
    "dtlx": ("scripts.builder.engines.dtlx", "DTLXEngine", EngineStage.PRE_PATCH),
    "lspatch": ("scripts.builder.engines.lspatch", "LSPatchEngine", EngineStage.PRE_PATCH),
    "rkpairip": ("scripts.builder.engines.rkpairip", "RKPairipEngine", EngineStage.PRE_PATCH),
    "whatsapp_patcher": ("scripts.builder.engines.whatsapp_patcher", "WhatsAppPatcherEngine", EngineStage.PRE_PATCH),
}


def get_available_engines() -> list[str]:
    """Return list of registered engine names."""
    return list(_ENGINE_REGISTRY.keys())


def get_engine_stage(name: str) -> EngineStage | None:
    """Return the pipeline stage for an engine."""
    entry = _ENGINE_REGISTRY.get(name)
    if entry is None:
        return None
    return entry[2]


def create_engine(name: str) -> Engine:
    """Instantiate a registered engine by name.

    Args:
        name: Engine name.

    Returns:
        Instantiated Engine object.

    Raises:
        ValueError: If engine name is unknown.
        ImportError: If engine module cannot be imported.
    """
    entry = _ENGINE_REGISTRY.get(name)
    if entry is None:
        raise ValueError(f"Unknown engine: {name}")

    module_path, class_name, _stage = entry
    module = __import__(module_path, fromlist=[class_name])
    engine_cls = getattr(module, class_name)
    return engine_cls()  # type: ignore[no-any-return]


class EngineRunner:
    """Runs registered engines at a specific pipeline stage."""

    def __init__(self, stage: EngineStage, enabled_engines: list[str]) -> None:
        """Initialize runner for a stage.

        Args:
            stage: Pipeline stage to execute.
            enabled_engines: List of engine names enabled for this build.
        """
        self.stage = stage
        self.enabled_engines = [
            name for name in enabled_engines if get_engine_stage(name) == stage
        ]

    def run(self, ctx: EngineContext) -> Path:
        """Execute all enabled engines for this stage in order.

        Args:
            ctx: Engine context with current_apk set.

        Returns:
            Path to the APK after all engines have run.

        Raises:
            RuntimeError: If any engine fails.
        """
        if not self.enabled_engines:
            return ctx.current_apk

        for name in self.enabled_engines:
            dispatch_plugins(ctx, f"pre_engine:{name}")
            ctx.log(f"Running {self.stage.value} engine: {name}")
            engine = create_engine(name)
            result = engine.run(ctx)

            if not result.success:
                msg = f"Engine {name} failed: {result.error or 'unknown error'}"
                ctx.log(msg, level=40)
                raise RuntimeError(msg)

            if result.output_apk is not None:
                ctx.current_apk = result.output_apk

            if result.metadata:
                ctx.metadata.setdefault(name, {}).update(result.metadata)

            ctx.log(f"Engine {name} completed")
            dispatch_plugins(ctx, f"post_engine:{name}")

        return ctx.current_apk
