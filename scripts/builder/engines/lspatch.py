"""LSPatch patching engine.

Ported from apk-tweak's lspatch engine.
Supports both binary CLI and JAR-based patching, module embedding,
and manager mode. Can run before ReVanced (complement) or replace it
(alternative) based on config.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from scripts.builder.engines import EngineContext, EngineResult, EngineStage


class LSPatchEngine:
    """Engine that patches APKs using LSPatch."""

    name = "lspatch"
    stage = EngineStage.PRE_PATCH

    def run(self, ctx: EngineContext) -> EngineResult:
        """Run the LSPatch engine.

        Args:
            ctx: Engine context.

        Returns:
            EngineResult with the patched APK path.
        """
        options = ctx.app_options.get(self.name, {})
        mode = str(ctx.global_options.get("lspatch_mode", "complement"))
        modules = list(options.get("modules", []))
        manager_mode = bool(options.get("manager_mode", False))
        use_cli = bool(options.get("use_cli", True))
        jar_path = str(options.get("jar_path", "lspatch.jar"))

        if not shutil.which("java"):
            return EngineResult(success=False, error="Java not found in PATH")

        work_dir = ctx.work_dir / self.name
        work_dir.mkdir(parents=True, exist_ok=True)
        output_dir = work_dir / "output"
        output_dir.mkdir(parents=True, exist_ok=True)

        # Prefer binary CLI if available.
        if use_cli and shutil.which("lspatch"):
            patched_apk = self._run_cli(
                ctx,
                ctx.current_apk,
                output_dir,
                modules,
                manager_mode,
            )
        else:
            patched_apk = self._run_jar(
                ctx,
                ctx.current_apk,
                output_dir,
                modules,
                manager_mode,
                jar_path,
            )

        if not patched_apk:
            return EngineResult(success=False, error="LSPatch did not produce an output APK")

        final_apk = ctx.output_dir / f"{ctx.current_apk.stem}.lspatch.apk"
        try:
            shutil.copy2(patched_apk, final_apk)
        except OSError as e:
            return EngineResult(success=False, error=f"Failed to copy LSPatch output: {e}")

        ctx.log(f"LSPatch: patching complete → {final_apk} (mode={mode})")
        return EngineResult(
            success=True,
            output_apk=final_apk,
            metadata={
                "modules": modules,
                "manager_mode": manager_mode,
                "mode": mode,
            },
        )

    def _run_cli(
        self,
        ctx: EngineContext,
        input_apk: Path,
        output_dir: Path,
        modules: list[str],
        manager_mode: bool,
    ) -> Path | None:
        """Run LSPatch binary CLI."""
        cmd = ["lspatch", "-v", "-l", "2", "-f", "-o", str(output_dir)]
        for module in modules:
            module_path = Path(module)
            if module_path.exists():
                cmd.extend(["-m", str(module_path)])
            else:
                ctx.log(f"LSPatch: module not found: {module}")
        if manager_mode:
            cmd.extend(["--manager", "--injectdex"])
        cmd.append(str(input_apk))

        ctx.log(f"LSPatch: running CLI → {output_dir}")
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=False,
                timeout=900,
            )
            if result.returncode == 0:
                return self._find_latest_apk(output_dir)
            ctx.log(f"LSPatch: CLI failed with code {result.returncode}")
        except (subprocess.TimeoutExpired, OSError) as e:
            ctx.log(f"LSPatch: CLI error: {e}")
        return None

    def _run_jar(
        self,
        ctx: EngineContext,
        input_apk: Path,
        output_dir: Path,
        modules: list[str],
        manager_mode: bool,
        jar_path: str,
    ) -> Path | None:
        """Run LSPatch JAR."""
        jar = Path(jar_path)
        if not jar.exists():
            return None

        cmd = ["java", "-jar", str(jar), "-l", "2", "-o", str(output_dir)]
        for module in modules:
            module_path = Path(module)
            if module_path.exists():
                cmd.extend(["-m", str(module_path)])
        if manager_mode:
            cmd.extend(["--manager", "--injectdex"])
        cmd.append(str(input_apk))

        ctx.log("LSPatch: using JAR-based approach")
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=False,
                timeout=900,
            )
            if result.returncode == 0:
                return self._find_latest_apk(output_dir)
            ctx.log(f"LSPatch: JAR failed with code {result.returncode}")
        except (subprocess.TimeoutExpired, OSError) as e:
            ctx.log(f"LSPatch: JAR error: {e}")
        return None

    def _find_latest_apk(self, directory: Path) -> Path | None:
        """Find the newest APK in a directory."""
        apk_files = [p for p in directory.glob("*.apk") if p.is_file()]
        if not apk_files:
            return None
        return max(apk_files, key=lambda p: p.stat().st_mtime)
