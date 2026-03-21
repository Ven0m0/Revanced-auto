"""Logging functions matching Bash script style."""

import os
import sys


def _is_debug() -> bool:
    return os.environ.get("DEBUG", "") not in ("", "0", "false", "False")


def debug(msg: str) -> None:
    if _is_debug():
        print(f"[DEBUG] {msg}", file=sys.stdout)


def info(msg: str) -> None:
    print(f"[INFO] {msg}", file=sys.stdout)


def warn(msg: str) -> None:
    print(f"[WARN] {msg}", file=sys.stderr)


def error(msg: str) -> None:
    print(f"[ERROR] {msg}", file=sys.stderr)


def epr(msg: str) -> None:
    print(f"[ERROR] {msg}", file=sys.stderr)


def pr(msg: str) -> None:
    print(msg, file=sys.stdout)


def abort(msg: str, code: int = 1) -> None:
    print(f"[ABORT] {msg}", file=sys.stderr)
    sys.exit(code)
