"""DTL-X analysis and optimization engine.

Ported from apk-tweak's dtlx engine.
Integrates with Gameye98/DTL-X for APK reverser/patcher tasks.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

from scripts.builder.engines import EngineContext, EngineResult, EngineStage

DTLX_REPO_URL = "https://github.com/Gameye98/DTL-X"

# All available DTL-X flags mapped to pipeline option names.
DTLX_FLAGS: dict[str, str] = {
    "rmads1": "--rmads1",
    "rmads2": "--rmads2",
    "rmads3": "--rmads3",
    "rmads4": "--rmads4",
    "rmads5": "--rmads5",
    "rmtrackers": "--rmtrackers",
    "rmnop": "--rmnop",
    "rmnown": "--rmnown",
    "sslbypass": "--sslbypass",
    "rmcopy": "--rmcopy",
    "rmvpndet": "--rmvpndet",
    "rmusbdebug": "--rmusbdebug",
    "rmssrestrict": "--rmssrestrict",
    "rmrootxposedvpn": "--rmrootxposedvpn",
    "rmexportdata": "--rmexportdata",
    "rmpairip": "--rmpairip",
    "bppairip": "--bppairip",
    "rmprop": "--rmprop",
    "nokill": "--nokill",
    "fixinstall": "--fixinstall",
    "obfuscatemethods": "--obfuscatemethods",
    "mergeobb": "--mergeobb",
    "injectdocsprovider": "--injectdocsprovider",
    "il2cppdumper": "--il2cppdumper",
    "cloneapk": "--cloneapk",
    "cleanrun": "--cleanrun",
    "nocompile": "--nocompile",
}

DEFAULT_OPTIMIZATION_FLAGS = ["rmads4", "rmtrackers", "rmnop", "cleanrun"]


class DTLXEngine:
    """Engine that analyzes and optimizes APKs using DTL-X."""

    name = "dtlx"
    stage = EngineStage.PRE_PATCH

    def run(self, ctx: EngineContext) -> EngineResult:
        """Run the DTL-X engine.

        Args:
            ctx: Engine context.

        Returns:
            EngineResult with the optimized APK path.
        """
        options = ctx.app_options.get(self.name, {})
        analyze = bool(options.get("dtlx_analyze", False))
        optimize = bool(options.get("dtlx_optimize", False))

        if not analyze and not optimize:
            ctx.log("DTL-X: nothing to do")
            return EngineResult(success=True, output_apk=ctx.current_apk)

        dtlx_path = self._find_dtlx(options.get("dtlx_path"))
        if not dtlx_path:
            return EngineResult(
                success=False,
                error=f"DTL-X not found. Install from {DTLX_REPO_URL}",
            )

        work_dir = ctx.work_dir / self.name
        work_dir.mkdir(parents=True, exist_ok=True)

        if analyze:
            report_file = work_dir / f"{ctx.current_apk.stem}-dtlx-report.txt"
            self._analyze(ctx, dtlx_path, ctx.current_apk, report_file)

        if optimize:
            return self._optimize(ctx, dtlx_path, ctx.current_apk, work_dir, options)

        return EngineResult(success=True, output_apk=ctx.current_apk)

    def _find_dtlx(self, configured_path: str | None) -> Path | None:
        """Locate DTL-X executable."""
        if configured_path:
            path = Path(configured_path)
            if path.is_file():
                return path

        locations = [
            Path.home() / "DTL-X" / "dtlx.py",
            Path("/opt/DTL-X/dtlx.py"),
            Path("/usr/local/bin/dtlx.py"),
        ]
        for loc in locations:
            if loc.is_file():
                return loc

        dtlx_path = shutil.which("dtlx.py")
        return Path(dtlx_path) if dtlx_path else None

    def _analyze(
        self,
        ctx: EngineContext,
        dtlx_path: Path,
        apk: Path,
        report_file: Path,
    ) -> bool:
        """Run DTL-X analysis mode."""
        ctx.log(f"DTL-X: analyzing {apk.name}")
        try:
            result = subprocess.run(
                [sys.executable, str(dtlx_path), str(apk)],
                capture_output=True,
                text=True,
                timeout=300,
                check=False,
            )
            report_content = [
                f"DTL-X Analysis Report for {apk.name}",
                "=" * 60,
                "",
                f"Exit Code: {result.returncode}",
                "",
                "STDOUT:",
                "-" * 60,
                result.stdout or "(no output)",
                "",
            ]
            if result.stderr:
                report_content.extend([
                    "STDERR:",
                    "-" * 60,
                    result.stderr,
                    "",
                ])
            report_file.write_text("\n".join(report_content), encoding="utf-8")
            ctx.log(f"DTL-X: analysis report saved to {report_file}")
            return True
        except (subprocess.TimeoutExpired, OSError) as e:
            report_file.write_text(
                f"DTL-X Analysis Report for {apk.name}\n{'=' * 60}\n\nStatus: ERROR\nError: {e}",
                encoding="utf-8",
            )
            return False

    def _optimize(
        self,
        ctx: EngineContext,
        dtlx_path: Path,
        apk: Path,
        work_dir: Path,
        options: dict,
    ) -> EngineResult:
        """Run DTL-X optimization mode."""
        flags = self._build_flags(options)
        ctx.log(f"DTL-X: optimizing {apk.name} with flags: {' '.join(flags)}")

        work_apk = work_dir / apk.name
        try:
            shutil.copy2(apk, work_apk)
        except OSError as e:
            return EngineResult(success=False, error=f"Failed to copy APK: {e}")

        try:
            result = subprocess.run(
                [sys.executable, str(dtlx_path)] + flags + [str(work_apk)],
                capture_output=True,
                text=True,
                timeout=600,
                cwd=work_dir,
                check=False,
            )
            if result.returncode != 0:
                error = result.stderr or result.stdout or "unknown error"
                return EngineResult(success=False, error=f"DTL-X optimization failed: {error}")
        except (subprocess.TimeoutExpired, OSError) as e:
            return EngineResult(success=False, error=f"DTL-X optimization error: {e}")

        # DTL-X typically produces output with suffixes like _signed.apk.
        output_apk = self._find_output_apk(work_dir, apk)
        if not output_apk:
            return EngineResult(success=False, error="DTL-X did not produce an output APK")

        final_apk = ctx.output_dir / f"{apk.stem}.dtlx.apk"
        try:
            shutil.copy2(output_apk, final_apk)
        except OSError as e:
            return EngineResult(success=False, error=f"Failed to copy output APK: {e}")

        ctx.log(f"DTL-X: optimization complete → {final_apk}")
        return EngineResult(success=True, output_apk=final_apk, metadata={"flags": flags})

    def _build_flags(self, options: dict) -> list[str]:
        """Build DTL-X flags from options."""
        flags: list[str] = []
        for opt_name, flag in DTLX_FLAGS.items():
            if options.get(opt_name):
                flags.append(flag)
        if not flags:
            flags = [DTLX_FLAGS[f] for f in DEFAULT_OPTIMIZATION_FLAGS]
        return flags

    def _find_output_apk(self, work_dir: Path, input_apk: Path) -> Path | None:
        """Find the most likely DTL-X output APK."""
        candidates = [
            work_dir / f"{input_apk.stem}_signed.apk",
            work_dir / f"{input_apk.stem}.apk",
        ]
        for candidate in candidates:
            if candidate.exists():
                return candidate

        # Fallback: newest APK in work dir, excluding the input APK.
        apk_files = [
            p for p in work_dir.glob("*.apk")
            if p.is_file() and p.name != input_apk.name
        ]
        if apk_files:
            return max(apk_files, key=lambda p: p.stat().st_mtime)
        return None
