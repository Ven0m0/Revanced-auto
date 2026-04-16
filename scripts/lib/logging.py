"""Logging functions matching Bash script style."""

import os
import sys
from typing import NoReturn


def _is_debug() -> bool:
    """Return whether debug logging is enabled."""
    return os.environ.get("DEBUG", "") not in ("", "0", "false", "False")


def debug(msg: str) -> None:
    """Print a debug message when debug logging is enabled."""
    if _is_debug():
        print(f"[DEBUG] {msg}", file=sys.stdout)


def info(msg: str) -> None:
    """Print an informational message."""
    print(f"[INFO] {msg}", file=sys.stdout)


def warn(msg: str) -> None:
    """Print a warning message."""
    print(f"[WARN] {msg}", file=sys.stderr)


def error(msg: str) -> None:
    """Print an error message."""
    print(f"[ERROR] {msg}", file=sys.stderr)


def epr(msg: str) -> None:
    """Print an error message to stderr."""
    print(f"[ERROR] {msg}", file=sys.stderr)


def pr(msg: str) -> None:
    """Print a plain message to stdout."""
    print(msg, file=sys.stdout)


def abort(msg: str, code: int = 1) -> NoReturn:
    """Print an abort message and terminate the process."""
    print(f"[ABORT] {msg}", file=sys.stderr)
    sys.exit(code)
