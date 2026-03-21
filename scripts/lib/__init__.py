"""scripts.lib - Bridge package for Bash-to-Python migration.

This package exists for backwards compatibility during the transition
from Bash to Python implementations.
"""

from scripts.lib import args
from scripts.lib import builder
from scripts.lib import config
from scripts.lib import logging
from scripts.lib import version_tracker

__all__ = ["args", "builder", "config", "logging", "version_tracker"]
