"""Plugin discovery and hook dispatch system.

Ported from apk-tweak's plugin architecture.
Plugins are auto-discovered from ``scripts/plugins/`` and can hook into
pipeline stages via ``handle_hook(ctx, stage)``.
"""

from __future__ import annotations

import importlib
import logging
import pkgutil
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:
    from scripts.builder.engines import EngineContext

PluginHandler = Callable[["EngineContext", str], None]

logger = logging.getLogger(__name__)
_PLUGIN_DIR = Path(__file__).parent.parent / "plugins"


def _discover_plugins() -> list[PluginHandler]:
    """Discover plugin modules and their hook handlers.

    Returns:
        List of callable plugin handlers.
    """
    handlers: list[PluginHandler] = []

    if not _PLUGIN_DIR.exists():
        return handlers

    # Ensure the plugins directory is importable.
    plugin_pkg_path = str(_PLUGIN_DIR.parent)
    if plugin_pkg_path not in sys.path:
        sys.path.insert(0, plugin_pkg_path)

    try:
        import scripts.plugins as plugins_pkg  # type: ignore[import-not-found]
    except ImportError:
        return handlers

    if not hasattr(plugins_pkg, "__path__"):
        return handlers

    for _finder, name, _ispkg in pkgutil.iter_modules(plugins_pkg.__path__):
        try:
            module = importlib.import_module(f"{plugins_pkg.__name__}.{name}")
            handler = getattr(module, "handle_hook", None)
            if callable(handler):
                handlers.append(handler)
                logger.debug("Loaded plugin: %s", name)
        except Exception as e:
            logger.warning("Plugin '%s' load failed: %s", name, e)

    return handlers


class PluginManager:
    """Manages plugin discovery and hook dispatch."""

    def __init__(self) -> None:
        """Initialize plugin manager and discover plugins."""
        self._handlers: list[PluginHandler] | None = None

    def _load(self) -> list[PluginHandler]:
        """Lazy-load discovered plugins."""
        if self._handlers is None:
            self._handlers = _discover_plugins()
        return self._handlers

    def dispatch(self, ctx: EngineContext, stage: str) -> None:
        """Dispatch a hook to all plugins.

        Errors from individual plugins are isolated so that one failing
        plugin does not break the pipeline.

        Args:
            ctx: Engine context.
            stage: Hook stage identifier.
        """
        for handler in self._load():
            try:
                handler(ctx, stage)
            except Exception as e:
                logger.error("Plugin hook error at '%s': %s", stage, e)


def dispatch_plugins(ctx: EngineContext, stage: str) -> None:
    """Convenience function to dispatch a plugin hook."""
    PluginManager().dispatch(ctx, stage)
