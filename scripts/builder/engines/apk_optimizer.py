"""APK optimizer engine for APK size reduction and cleanup.

Ported from apk-tweak's optimizer engine.
Removes debug symbols, strips native libraries, minimizes manifests,
cleans resources, and filters locales.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path

from scripts.builder.engines import EngineContext, EngineResult, EngineStage
from scripts.utils.apk_io import extract_apk, repack_apk

# Regex patterns for debug/symbol removal.
_DIR_PATTERNS = [
    r".*proguard.*",
    r".*debug.*",
    r".*Debug.*",
    r".*\/tests?(/.*|$)",
    r"^tests?(/.*|$)",
]

_FILE_PATTERNS = [
    r".*\.map$",
    r".*\.log$",
    r".*proguard.*",
    r".*mapping\.txt$",
    r".*debug.*",
    r".*Debug.*",
    r".*\/tests?(/.*|$)",
    r"^tests?(/.*|$)",
]

_DIR_REGEX = re.compile("|".join(f"(?:{p})" for p in _DIR_PATTERNS), re.IGNORECASE)
_FILE_REGEX = re.compile("|".join(f"(?:{p})" for p in _FILE_PATTERNS), re.IGNORECASE)


class APKOptimizerEngine:
    """Engine that performs general APK optimization and debloating."""

    name = "apk_optimizer"
    stage = EngineStage.POST_PATCH

    def run(self, ctx: EngineContext) -> EngineResult:
        """Run the APK optimizer engine.

        Args:
            ctx: Engine context.

        Returns:
            EngineResult with the optimized APK path.
        """
        options = ctx.app_options.get(self.name, {})
        remove_debug = bool(options.get("remove_debug_symbols", True))
        minimize_manifest = bool(options.get("minimize_manifest", True))
        optimize_resources = bool(options.get("optimize_resources", True))
        keep_locales = list(options.get("keep_locales", ["en"]))
        strip_native = bool(options.get("strip_native_libs", True))

        if not any([remove_debug, minimize_manifest, optimize_resources, strip_native]):
            ctx.log("APK optimizer: nothing to do")
            return EngineResult(success=True, output_apk=ctx.current_apk)

        work_dir = ctx.work_dir / self.name
        work_dir.mkdir(parents=True, exist_ok=True)
        extract_dir = work_dir / "extracted"

        ctx.log(f"APK optimizer: extracting {ctx.current_apk.name}")
        if not extract_apk(ctx.current_apk, extract_dir):
            return EngineResult(success=False, error="Failed to extract APK")

        stats: dict[str, int] = {
            "debug_removed": 0,
            "native_stripped": 0,
            "manifest_minimized": 0,
            "resource_cleaned": 0,
            "locales_removed": 0,
        }

        if remove_debug:
            stats["debug_removed"] = self._remove_debug_symbols(extract_dir)

        if strip_native:
            stats["native_stripped"] = self._strip_native_libraries(ctx, extract_dir)

        if minimize_manifest:
            stats["manifest_minimized"] = 1 if self._minimize_manifest(extract_dir) else 0

        if optimize_resources:
            stats["resource_cleaned"] = self._optimize_resources(extract_dir)

        if keep_locales:
            stats["locales_removed"] = self._remove_locale_resources(extract_dir, keep_locales)

        output_apk = ctx.output_dir / f"{ctx.current_apk.stem}.opt.apk"
        ctx.log(f"APK optimizer: repacking to {output_apk.name}")
        if not repack_apk(extract_dir, output_apk):
            return EngineResult(success=False, error="Failed to repack APK")

        ctx.log(
            f"APK optimizer: done (debug_removed={stats['debug_removed']}, "
            f"native_stripped={stats['native_stripped']}, "
            f"manifest_minimized={stats['manifest_minimized']}, "
            f"resource_cleaned={stats['resource_cleaned']}, "
            f"locales_removed={stats['locales_removed']})"
        )

        return EngineResult(success=True, output_apk=output_apk, metadata=stats)

    def _remove_debug_symbols(self, extract_dir: Path) -> int:
        """Remove debug symbols and unnecessary files."""
        removed_count = 0
        extract_dir_str = str(extract_dir)
        extract_dir_len = len(extract_dir_str) + 1

        for root, dirs, files in os.walk(extract_dir_str, topdown=True):
            root_path = Path(root)
            rel_dir = root[extract_dir_len:].replace(os.sep, "/")

            for i in range(len(dirs) - 1, -1, -1):
                d_name = dirs[i]
                rel_path = f"{rel_dir}/{d_name}" if rel_dir else d_name
                if _DIR_REGEX.match(rel_path) or _DIR_REGEX.match(f"{rel_path}/"):
                    try:
                        shutil.rmtree(root_path / d_name)
                        removed_count += 1
                        del dirs[i]
                    except OSError:
                        pass

            for f_name in files:
                rel_path = f"{rel_dir}/{f_name}" if rel_dir else f_name
                if _FILE_REGEX.match(rel_path):
                    try:
                        (root_path / f_name).unlink()
                        removed_count += 1
                    except OSError:
                        pass

        return removed_count

    def _strip_native_libraries(self, ctx: EngineContext, extract_dir: Path) -> int:
        """Strip debug symbols from native libraries."""
        if not shutil.which("strip"):
            ctx.log("APK optimizer: 'strip' not found, skipping native library stripping")
            return 0

        stripped_count = 0
        lib_dir = extract_dir / "lib"
        if not lib_dir.exists():
            return 0

        for so_file in lib_dir.rglob("*.so"):
            if not so_file.is_file():
                continue
            try:
                result = subprocess.run(
                    ["strip", "--strip-unneeded", str(so_file)],
                    capture_output=True,
                    text=True,
                    check=False,
                    timeout=60,
                )
                if result.returncode == 0:
                    stripped_count += 1
            except (OSError, subprocess.SubprocessError):
                pass

        return stripped_count

    def _minimize_manifest(self, extract_dir: Path) -> bool:
        """Remove XML comments from plain-text AndroidManifest.xml."""
        manifest_path = extract_dir / "AndroidManifest.xml"
        if not manifest_path.exists():
            return False

        try:
            raw_content = manifest_path.read_bytes()
        except OSError:
            return False

        try:
            content = raw_content.decode("utf-8")
        except UnicodeDecodeError:
            return False

        if not content.lstrip().startswith("<"):
            return False

        content = re.sub(r"<!--.*?-->", "", content, flags=re.DOTALL)

        try:
            manifest_path.write_text(content, encoding="utf-8")
            return True
        except OSError:
            return False

    def _optimize_resources(self, extract_dir: Path) -> int:
        """Remove unnecessary resource files."""
        res_dir = extract_dir / "res"
        if not res_dir.exists():
            return 0

        removed_count = 0
        for root, _dirs, files in os.walk(res_dir):
            for name in files:
                if name == ".DS_Store" or name.endswith("~"):
                    try:
                        (Path(root) / name).unlink()
                        removed_count += 1
                    except OSError:
                        pass

        return removed_count

    def _remove_locale_resources(self, extract_dir: Path, keep_locales: list[str]) -> int:
        """Remove locale-specific resources not in the keep list."""
        res_dir = extract_dir / "res"
        if not res_dir.exists():
            return 0

        keep_lower = {loc.lower() for loc in keep_locales}
        removed_count = 0

        for resource_dir in res_dir.iterdir():
            if not resource_dir.is_dir() or not resource_dir.name.startswith("values-"):
                continue
            locale_part = resource_dir.name[7:]  # Remove "values-" prefix
            locale_prefix = locale_part.split("-")[0].lower()
            if locale_prefix not in keep_lower:
                try:
                    shutil.rmtree(resource_dir)
                    removed_count += 1
                except OSError:
                    pass

        return removed_count
