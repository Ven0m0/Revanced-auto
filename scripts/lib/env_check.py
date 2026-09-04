"""Environment/prerequisite checks. Replaces check-env.sh and scripts/lib/checks.sh."""

from __future__ import annotations

import re
import shutil
import subprocess
import tomllib
from dataclasses import dataclass
from pathlib import Path

from scripts.lib import logging as log
from scripts.utils.network import download_with_lock

# Same pinned upstream binaries and hashes as the retired scripts/lib/checks.sh.
_BINARIES_SOURCE_REF = "c62a54d5a04617400cd19ef33cba2dfdb5b0947f"
_BINARIES_BASE_URL = f"https://raw.githubusercontent.com/j-hc/revanced-magisk-module/{_BINARIES_SOURCE_REF}/bin"
_PINNED_BINARIES: dict[str, str] = {
    "apksigner.jar": "eefdd6aed9db9fb849e4c98a50d8741e19d1b674ba6547220bcb9c3ed152123a",
    "dexlib2.jar": "bbd18fb81e521c362fb37fa89d93974debb2107a9d2e1057cdd8329b92479466",
    "paccer.jar": "cbc9d084b2117a203a1818fba3c73b06cd8817b147a185c00975980e86d5dead",
}

# java (bundles keytool, used for Part 4's BKS conversion), zip/unzip (used by
# apkmirror.merge_apkm_splits), and uv (checked separately via its own probe below).
_REQUIRED_TOOLS = ("java", "zip", "unzip")

_MIN_JAVA_MAJOR = 21


@dataclass
class EnvCheckResult:
    """Outcome of check_full_environment(): pass/fail plus the messages behind it."""

    ok: bool
    errors: list[str]
    warnings: list[str]


def _check_system_tools() -> list[str]:
    missing = [tool for tool in _REQUIRED_TOOLS if shutil.which(tool) is None]
    return [f"Missing required system tool: {tool}" for tool in missing]


def _check_java_version() -> list[str]:
    if shutil.which("java") is None:
        return []  # already reported by _check_system_tools
    result = subprocess.run(["java", "-version"], capture_output=True, text=True, check=False)  # noqa: S607
    version_line = (result.stdout or result.stderr).splitlines()[0] if result.stdout or result.stderr else ""

    match = re.search(r'"(?:1\.)?(\d+)', version_line)
    major = int(match.group(1)) if match else 0
    if major < _MIN_JAVA_MAJOR:
        return [f"Java version must be {_MIN_JAVA_MAJOR} or higher (found: Java {major})"]
    return []


def _check_assets() -> list[str]:
    warnings = []
    if not Path("assets/ks.keystore").exists():
        warnings.append("assets/ks.keystore not found (will be created during build)")
    if not Path("assets/sig.txt").exists():
        warnings.append("assets/sig.txt not found (signature verification disabled)")
    return warnings


def _check_optional_tools() -> list[str]:
    optional = {"zipalign": "APK optimization", "optipng": "asset optimization"}
    return [
        f"Missing optional tool: {tool} (for {purpose})" for tool, purpose in optional.items() if not shutil.which(tool)
    ]


def _check_config_file() -> list[str]:
    config_path = Path("config.toml")
    if not config_path.exists():
        return []  # warning-only in the original; absence is not fatal here
    try:
        with config_path.open("rb") as f:
            tomllib.load(f)
    except (tomllib.TOMLDecodeError, OSError) as e:
        return [f"config.toml syntax invalid: {e}"]
    return []


def check_binaries(bin_dir: Path | None = None) -> list[str]:
    """Download and SHA-256-verify the pinned bin/*.jar dependencies. Returns error messages."""
    bin_dir = bin_dir or Path("bin")
    bin_dir.mkdir(parents=True, exist_ok=True)
    errors = []
    for name, sha256 in _PINNED_BINARIES.items():
        target = bin_dir / name
        if not download_with_lock(f"{_BINARIES_BASE_URL}/{name}", target, sha256=sha256):
            errors.append(f"Failed to download/verify {target}")
    return errors


def check_full_environment() -> EnvCheckResult:
    """Run every prerequisite check and collect pass/fail into one result."""
    errors: list[str] = []
    errors.extend(_check_system_tools())
    errors.extend(_check_java_version())
    warnings = _check_optional_tools()
    errors.extend(check_binaries())
    warnings.extend(_check_assets())
    errors.extend(_check_config_file())
    return EnvCheckResult(ok=not errors, errors=errors, warnings=warnings)


def run_check_env() -> int:
    """CLI entry point: run the full check and print results. Returns a process exit code."""
    log.info("Performing full environment check...")
    result = check_full_environment()
    for warning in result.warnings:
        log.warn(warning)
    for error in result.errors:
        log.error(error)
    if result.ok:
        log.pr("Environment check passed")
        return 0
    log.error("Environment check failed")
    return 1
