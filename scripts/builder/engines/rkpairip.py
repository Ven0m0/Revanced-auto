"""RKPairip engine for advanced APK decompilation and rebuilding.

Ported from apk-tweak's rkpairip engine.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from scripts.builder.engines import EngineContext, EngineResult, EngineStage


class RKPairipEngine:
    """Engine that processes APKs using RKPairip."""

    name = "rkpairip"
    stage = EngineStage.PRE_PATCH

    def run(self, ctx: EngineContext) -> EngineResult:
        """Run the RKPairip engine.

        Args:
            ctx: Engine context.

        Returns:
            EngineResult with the processed APK path.
        """
        options = ctx.app_options.get(self.name, {})
        use_apktool = bool(options.get("apktool_mode", False))
        merge_skip = bool(options.get("merge_skip", False))
        dex_repair = bool(options.get("dex_repair", False))
        corex_hook = bool(options.get("corex_hook", False))
        anti_split = bool(options.get("anti_split", False))

        if not shutil.which("RKPairip"):
            return EngineResult(
                success=False,
                error="RKPairip not found in PATH. Install via: pip install Pairip",
            )

        work_dir = ctx.work_dir / self.name
        work_dir.mkdir(parents=True, exist_ok=True)

        cmd = ["RKPairip", "-i", str(ctx.current_apk)]
        if use_apktool:
            cmd.append("-a")
            ctx.log("RKPairip: ApkTool mode enabled")
        if merge_skip:
            cmd.append("-s")
            ctx.log("RKPairip: merge skip mode enabled")
        if dex_repair:
            cmd.append("-r")
            ctx.log("RKPairip: DEX repair enabled")
        if corex_hook:
            cmd.append("-x")
            ctx.log("RKPairip: CoreX hook enabled")
        if anti_split:
            cmd.append("-m")
            ctx.log("RKPairip: anti-split merge mode enabled")

        ctx.log(f"RKPairip: executing {' '.join(cmd)}")
        try:
            result = subprocess.run(
                cmd,
                cwd=work_dir,
                capture_output=True,
                text=True,
                check=False,
                timeout=1200,
            )
            if result.returncode != 0:
                return EngineResult(
                    success=False,
                    error=f"RKPairip failed (code {result.returncode}): {result.stderr}",
                )
        except (subprocess.TimeoutExpired, OSError) as e:
            return EngineResult(success=False, error=f"RKPairip error: {e}")

        output_apk = self._find_output_apk(work_dir)
        if not output_apk:
            return EngineResult(success=False, error="RKPairip did not produce an output APK")

        final_apk = ctx.output_dir / f"{ctx.current_apk.stem}.rkpairip.apk"
        try:
            shutil.copy2(output_apk, final_apk)
        except OSError as e:
            return EngineResult(success=False, error=f"Failed to copy output APK: {e}")

        ctx.log(f"RKPairip: complete → {final_apk}")
        return EngineResult(
            success=True,
            output_apk=final_apk,
            metadata={
                "apktool_mode": use_apktool,
                "merge_skip": merge_skip,
                "dex_repair": dex_repair,
                "corex_hook": corex_hook,
                "anti_split": anti_split,
            },
        )

    def _find_output_apk(self, work_dir: Path) -> Path | None:
        """Find newest APK produced by RKPairip."""
        apk_files = [p for p in work_dir.glob("*.apk") if p.is_file()]
        if not apk_files:
            return None
        return max(apk_files, key=lambda p: p.stat().st_mtime)
