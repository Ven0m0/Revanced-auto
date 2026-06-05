#!/usr/bin/env python3
"""ReVanced APK patching module.

Orchestrates the patching process using ReVanced CLI to patch APKs with
support for multiple patch sources, signature verification, and optimizations.

Exit codes:
    0: Success
    1: Error (patching, signing, or verification failure)
"""

from __future__ import annotations

import concurrent.futures
import hashlib
import logging
import os
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

from scripts.builder.cli_profiles import (
    REVANCED_CLI_V6,
    CLIProfile,
    PatchCommandConfig,
)
from scripts.builder.config import AppConfig
from scripts.utils.apk import APKSigner, align_apk, verify_signature
from scripts.utils.java import JavaRunner

logger = logging.getLogger(__name__)

CACHE_TTL_DEFAULT = 86400

RIP_LIB_ARCH_PATTERNS = {
    "arm64-v8a": ["armeabi-v7a"],
    "arm-v7a": ["arm64-v8a"],
    "x86_64": ["x86"],
    "x86": ["x86_64"],
}


@dataclass
class PatcherConfig:
    """Configuration for the patching process."""

    keystore_path: Path
    keystore_password: str
    key_alias: str
    key_password: str
    enable_riplib: bool = True
    enable_aapt2_optimize: bool = True
    custom_aapt2_binary: Path | None = None
    rv_brand: str = "rv"


@dataclass
class PatcherResult:
    """Result of a patching operation."""

    success: bool
    output_apk: Path | None = None
    version: str | None = None
    error: str | None = None


class CacheManager:
    """Manages caching for patch lists and other temporary data."""

    def __init__(self, cache_dir: Path | None = None) -> None:
        if cache_dir is None:
            cache_dir = Path(tempfile.gettempdir()) / "rv-cache"
        self._cache_dir = cache_dir
        self._cache_dir.mkdir(parents=True, exist_ok=True)

    def get_cache_path(self, key: str, subdir: str | None = None) -> Path:
        safe_key = hashlib.sha256(key.encode()).hexdigest()[:32]
        if subdir:
            cache_path = self._cache_dir / subdir / safe_key
            cache_path.parent.mkdir(parents=True, exist_ok=True)
        else:
            cache_path = self._cache_dir / safe_key
        return cache_path

    def cache_is_valid(self, cache_path: Path, ttl: int = CACHE_TTL_DEFAULT) -> bool:
        if not cache_path.exists():
            return False
        import time

        mtime = cache_path.stat().st_mtime
        age = time.time() - mtime
        return age < ttl

    def cache_put(self, cache_path: Path) -> None:
        if cache_path.exists():
            os.utime(cache_path, None)


def _get_file_hash(file_path: Path) -> str | None:
    try:
        with open(file_path, "rb") as f:
            return hashlib.file_digest(f, "sha256").hexdigest()
    except OSError:
        return None


class ReVancedPatcher:
    """Orchestrates the ReVanced APK patching process."""

    def __init__(
        self,
        config: AppConfig,
        cli_profile: CLIProfile,
        java_runner: JavaRunner,
        patcher_config: PatcherConfig,
        cache_manager: CacheManager | None = None,
    ) -> None:
        self.config = config
        self.cli_profile = cli_profile
        self.java_runner = java_runner
        self.patcher_config = patcher_config
        self._cache_manager = cache_manager or CacheManager()

    def patch(
        self,
        stock_apk: Path,
        output_apk: Path,
        cli_jar: Path,
        patches_jars: list[Path],
        version: str,
        arch: str,
        exclude_patches: list[str] | None = None,
        include_patches: list[str] | None = None,
        merge_jars: list[Path] | None = None,
        patches_post: list[Path] | None = None,
        force: bool = False,
    ) -> PatcherResult:
        error = self._verify_inputs(stock_apk, cli_jar, patches_jars)
        if error:
            return PatcherResult(success=False, error=error)

        exclude_patches = exclude_patches or []
        include_patches = include_patches or []
        merge_jars = merge_jars or []
        patches_post = patches_post or []

        output_apk.parent.mkdir(parents=True, exist_ok=True)

        signature = verify_signature(stock_apk)
        if signature is None:
            logger.warning("Could not verify stock APK signature, proceeding anyway")

        cli_args = self._build_patch_args(
            stock_apk=stock_apk,
            output_apk=output_apk,
            patches_jars=patches_jars,
            exclude_patches=exclude_patches,
            include_patches=include_patches,
            merge_jars=merge_jars,
            patches_post=patches_post,
            force=force,
        )

        result = self._execute_patch_command(cli_jar, cli_args)
        if result:
            return result

        if not output_apk.exists():
            return PatcherResult(success=False, error="Patching succeeded but output APK not found")

        result = self._sign_apk(output_apk)
        if result:
            return result

        self._zipalign_apk(output_apk)

        return PatcherResult(success=True, output_apk=output_apk, version=version)

    def _verify_inputs(self, stock_apk: Path, cli_jar: Path, patches_jars: list[Path]) -> str | None:
        """Verify that all input files exist."""
        if not stock_apk.exists():
            return f"Stock APK not found: {stock_apk}"

        if not cli_jar.exists():
            return f"CLI JAR not found: {cli_jar}"

        for jar in patches_jars:
            if not jar.exists():
                return f"Patches JAR not found: {jar}"

        return None

    def _execute_patch_command(self, cli_jar: Path, cli_args: list[str]) -> PatcherResult | None:
        """Execute the ReVanced CLI patch command."""
        logger.info("Executing: java -jar %s patch %s", cli_jar.name, " ".join(cli_args))

        env = os.environ.copy()
        env.pop("GITHUB_REPOSITORY", None)
        env["RV_KEYSTORE_PASSWORD"] = self.patcher_config.keystore_password
        env["RV_KEYSTORE_ENTRY_PASSWORD"] = self.patcher_config.key_password

        cmd = ["java"] + self.java_runner.java_args + ["-jar", str(cli_jar), "patch"] + cli_args

        try:
            result = subprocess.run(
                cmd,
                env=env,
                capture_output=True,
                text=True,
                timeout=600,
            )
            logger.debug("Return code: %d", result.returncode)
            if result.stdout:
                logger.debug("stdout: %s", result.stdout)
            if result.stderr:
                logger.debug("stderr: %s", result.stderr)

            if result.returncode != 0:
                return PatcherResult(
                    success=False,
                    error=f"Patching failed with return code {result.returncode}",
                )
        except subprocess.TimeoutExpired:
            return PatcherResult(success=False, error="Patching timed out after 600 seconds")
        except OSError as e:
            return PatcherResult(success=False, error=f"Failed to execute Java: {e}")

        return None

    def _sign_apk(self, output_apk: Path) -> PatcherResult | None:
        """Re-sign the patched APK."""
        temp_signed = output_apk.parent / f"{output_apk.stem}.tmp-signed.apk"
        try:
            signer = APKSigner(
                keystore=self.patcher_config.keystore_path,
                keystore_password=self.patcher_config.keystore_password,
                key_alias=self.patcher_config.key_alias,
                key_password=self.patcher_config.key_password,
            )
            if not signer.sign(output_apk, temp_signed):
                temp_signed.unlink(missing_ok=True)
                return PatcherResult(success=False, error="Re-signing with apksigner failed")

            temp_signed.replace(output_apk)
            logger.info("APK re-signed successfully with v1+v2 signature scheme")
        except OSError as e:
            temp_signed.unlink(missing_ok=True)
            return PatcherResult(success=False, error=f"Failed to re-sign APK: {e}")

        return None

    def _zipalign_apk(self, output_apk: Path) -> None:
        """Zipalign the signed APK."""
        aligned_apk = output_apk.parent / f"{output_apk.stem}-aligned.apk"
        if align_apk(output_apk, aligned_apk):
            aligned_apk.replace(output_apk)
            logger.info("APK successfully zipaligned")
        else:
            logger.warning("zipalign failed, continuing with unaligned APK")
            aligned_apk.unlink(missing_ok=True)

    def _build_patch_args(
        self,
        stock_apk: Path,
        output_apk: Path,
        patches_jars: list[Path],
        exclude_patches: list[str],
        include_patches: list[str],
        merge_jars: list[Path],
        patches_post: list[Path],
        force: bool,
    ) -> list[str]:
        args: list[str] = self.cli_profile.build_patch_args(
            PatchCommandConfig(
                apk_path=stock_apk,
                output_path=output_apk,
                patches_jars=patches_jars,
                patches_post=patches_post,
                exclude=exclude_patches,
                include=include_patches,
                merge=merge_jars,
                keystore=self.patcher_config.keystore_path,
                force=force,
                purge=True,
            )
        )

        args.extend(
            [
                "--keystore-password=env:RV_KEYSTORE_PASSWORD",
                "--keystore-entry-password=env:RV_KEYSTORE_ENTRY_PASSWORD",
                "--signer",
                self.patcher_config.key_alias,
                "--keystore-entry-alias",
                self.patcher_config.key_alias,
            ]
        )

        if self.patcher_config.custom_aapt2_binary and self.patcher_config.custom_aapt2_binary.exists():
            args.append(f"--custom-aapt2-binary={self.patcher_config.custom_aapt2_binary}")
            logger.debug("Using custom aapt2 binary: %s", self.patcher_config.custom_aapt2_binary)

        return args

    def list_patches(self, patches_jar: Path, cli_jar: Path) -> str:
        cmd = ["java"] + self.java_runner.java_args + ["-jar", str(cli_jar), "list-patches", str(patches_jar), "-v"]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60,
            )
            return result.stdout + result.stderr
        except (subprocess.TimeoutExpired, OSError) as e:
            logger.error("Failed to list patches: %s", e)
            return ""

    def get_supported_version(
        self,
        pkg_name: str,
        patches_jars: list[Path],
        cli_jar: Path,
        include_patches: list[str] | None = None,
        exclude_patches: list[str] | None = None,
    ) -> str | None:
        list_output = self.get_cached_patches_list(cli_jar, patches_jars)
        if not list_output:
            return None

        return self._parse_version_from_patches(list_output, pkg_name, include_patches, exclude_patches)

    def _parse_version_from_patches(
        self,
        list_output: str,
        pkg_name: str,
        include_patches: list[str] | None = None,
        exclude_patches: list[str] | None = None,
    ) -> str | None:
        lines = list_output.splitlines()
        in_package = False
        version: str | None = None

        for line in lines:
            if line.startswith("Package: ") and pkg_name in line:
                in_package = True
                continue

            if in_package:
                if line.startswith("Package: "):
                    break
                if line.startswith("Version: "):
                    ver = line.split("Version: ", 1)[1].strip()
                    if version is None or self._version_compare(ver, version) > 0:
                        version = ver

        return version

    def _version_compare(self, v1: str, v2: str) -> int:
        parts1 = [int(p) for p in v1.split(".") if p.isdigit()]
        parts2 = [int(p) for p in v2.split(".") if p.isdigit()]

        for p1, p2 in zip(parts1, parts2):
            if p1 < p2:
                return -1
            if p1 > p2:
                return 1

        if len(parts1) < len(parts2):
            return -1
        if len(parts1) > len(parts2):
            return 1

        return 0

    def get_cached_patches_list(
        self,
        cli_jar: Path,
        patches_jars: list[Path],
    ) -> str:
        if not cli_jar.exists():
            logger.warning("get_cached_patches_list: CLI JAR not found")
            return ""

        cli_hash = _get_file_hash(cli_jar)
        if cli_hash is None:
            logger.warning("Failed to get hash for CLI JAR")
            return ""

        patches_hashes: list[str] = []
        if patches_jars:
            for jar in patches_jars:
                if not jar.exists():
                    logger.warning("get_cached_patches_list: JAR not found: %s", jar)
                    return ""
            with concurrent.futures.ThreadPoolExecutor() as executor:
                for i, jar_hash in enumerate(executor.map(_get_file_hash, patches_jars)):
                    if jar_hash is None:
                        logger.warning("Failed to get hash for: %s", patches_jars[i])
                        return ""
                    patches_hashes.append(jar_hash)

        cache_key = f"patches-list-{cli_hash}-{'+'.join(patches_hashes)}"
        cache_path = self._cache_manager.get_cache_path(cache_key, subdir="patches")

        if self._cache_manager.cache_is_valid(cache_path):
            logger.debug("Using cached patch list: %s", cache_path)
            try:
                return cache_path.read_text(encoding="utf-8")
            except OSError:
                pass

        logger.debug("Generating patch list cache...")

        temp_file = cache_path.parent / f"tmp.{cache_path.name}"
        try:
            cmd = ["java"] + self.java_runner.java_args + ["-jar", str(cli_jar), "list-patches"]
            for jar in patches_jars:
                cmd.extend(["-p", str(jar)])
            cmd.append("-v")

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60,
            )

            if result.returncode != 0:
                logger.warning("Failed to list patches: %s", result.stderr)
                return ""

            temp_file.write_text(result.stdout + result.stderr, encoding="utf-8")
            temp_file.replace(cache_path)
            self._cache_manager.cache_put(cache_path)

            return result.stdout + result.stderr
        except (subprocess.TimeoutExpired, OSError) as e:
            logger.warning("Failed to generate patch list cache: %s", e)
            temp_file.unlink(missing_ok=True)
            return ""

    def determine_version(
        self,
        version_mode: str,
        pkg_name: str,
        patches_jars: list[Path],
        cli_jar: Path,
        include_patches: list[str] | None = None,
        exclude_patches: list[str] | None = None,
        version_override: str | None = None,
    ) -> str | None:
        if version_mode == "auto":
            logger.info("Auto-detecting compatible version")
            version = self.get_supported_version(
                pkg_name=pkg_name,
                patches_jars=patches_jars,
                cli_jar=cli_jar,
                include_patches=include_patches,
                exclude_patches=exclude_patches,
            )
            if version:
                logger.info("Detected version: %s", version)
                return version
            logger.debug("No specific version required, using latest")
            version_mode = "latest"
        else:
            version = version_override

        return version

    def handle_microg_patch(
        self,
        patches_jars: list[Path],
        cli_jar: Path,
        exclude_patches: list[str],
        include_patches: list[str],
    ) -> tuple[list[str], list[str], str | None]:
        list_output = self.get_cached_patches_list(cli_jar, patches_jars)
        microg_patch: str | None = None

        for line in list_output.splitlines():
            if line.startswith("Name: "):
                patch_name = line.split("Name: ", 1)[1].strip().lower()
                if "gmscore" in patch_name or "microg" in patch_name:
                    microg_patch = line.split("Name: ", 1)[1].strip()
                    break

        if microg_patch:
            if microg_patch in exclude_patches:
                exclude_patches = [p for p in exclude_patches if p != microg_patch]
                logger.warning(
                    "Cannot exclude microg patch '%s', removing from exclusions",
                    microg_patch,
                )
            if microg_patch in include_patches:
                include_patches = [p for p in include_patches if p != microg_patch]
                logger.warning(
                    "Cannot include microg patch '%s', removing from inclusions",
                    microg_patch,
                )

        return exclude_patches, include_patches, microg_patch

    def apply_riplib_optimization(self, arch: str) -> list[str]:
        if not self.patcher_config.enable_riplib:
            return []

        logger.info("Applying library stripping optimization")
        rip_libs: list[str] = []

        if arch in RIP_LIB_ARCH_PATTERNS:
            for pattern in RIP_LIB_ARCH_PATTERNS[arch]:
                rip_libs.append(pattern)

        return rip_libs

    def get_output_filename(
        self,
        app_name: str,
        version: str,
        arch: str,
    ) -> str:
        brand = self.patcher_config.rv_brand.lower().replace(" ", "-")
        app_clean = app_name.lower().replace(" ", "-")
        version_clean = version.replace(".", "_")
        arch_clean = arch.replace(" ", "")
        return f"{app_clean}-{brand}-v{version_clean}-{arch_clean}.apk"


def main(argv: list[str]) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="ReVanced Patcher")
    parser.add_argument("--stock-apk", type=Path, required=True, help="Input APK path")
    parser.add_argument("--output-apk", type=Path, required=True, help="Output APK path")
    parser.add_argument("--cli-jar", type=Path, required=True, help="ReVanced CLI JAR path")
    parser.add_argument("--patches-jar", type=Path, nargs="+", required=True, help="Patches JAR path(s)")
    parser.add_argument("--version", type=str, required=True, help="Version string")
    parser.add_argument("--arch", type=str, default="arm64-v8a", help="Target architecture")
    parser.add_argument("--keystore", type=Path, required=True, help="Keystore path")
    parser.add_argument("--keystore-password", type=str, required=True, help="Keystore password")
    parser.add_argument("--key-alias", type=str, required=True, help="Key alias")
    parser.add_argument("--key-password", type=str, required=True, help="Key password")

    args = parser.parse_args(argv[1:])

    patcher_config = PatcherConfig(
        keystore_path=args.keystore,
        keystore_password=args.keystore_password,
        key_alias=args.key_alias,
        key_password=args.key_password,
    )

    app_config = AppConfig(name="app")
    java_runner = JavaRunner()
    cli_profile = REVANCED_CLI_V6

    patcher = ReVancedPatcher(
        config=app_config,
        cli_profile=cli_profile,
        java_runner=java_runner,
        patcher_config=patcher_config,
    )

    result = patcher.patch(
        stock_apk=args.stock_apk,
        output_apk=args.output_apk,
        cli_jar=args.cli_jar,
        patches_jars=args.patches_jar,
        version=args.version,
        arch=args.arch,
    )

    if result.success:
        print(f"Successfully patched APK: {result.output_apk}")
        return 0
    print(f"Error: {result.error}", file=__import__("sys").stderr)
    return 1


if __name__ == "__main__":
    import sys

    sys.exit(main(sys.argv))
