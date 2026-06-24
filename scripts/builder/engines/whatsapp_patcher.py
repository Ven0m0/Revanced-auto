"""WhatsApp patcher engine.

Ported from apk-tweak's whatsapp engine.
Patches WhatsApp Android APK using Schwartzblat/WhatsAppPatcher.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

from scripts.builder.engines import EngineContext, EngineResult, EngineStage

WHATSAPP_PATCHER_REPO = "https://github.com/Schwartzblat/WhatsAppPatcher"
WHATSAPP_PATCHER_COMMIT = "3282dbb"
WHATSAPP_FEATURES = [
    "Signature Verifier Bypass",
    "Enable all AB tests",
    "Keep revoked for all messages",
    "Disable read receipts",
    "Save view once media",
]


class WhatsAppPatcherEngine:
    """Engine that patches WhatsApp APKs."""

    name = "whatsapp_patcher"
    stage = EngineStage.PRE_PATCH

    def run(self, ctx: EngineContext) -> EngineResult:
        """Run the WhatsApp patcher engine.

        Args:
            ctx: Engine context.

        Returns:
            EngineResult with the patched APK path.
        """
        options = ctx.app_options.get(self.name, {})
        patcher_path = options.get("patcher_path")
        ab_tests = bool(options.get("ab_tests", True))
        timeout = int(options.get("timeout", 1200))

        if not shutil.which("java"):
            return EngineResult(success=False, error="Java not found in PATH")

        work_dir = ctx.work_dir / self.name
        work_dir.mkdir(parents=True, exist_ok=True)

        if patcher_path:
            patcher_dir = Path(patcher_path)
        else:
            patcher_dir = work_dir / "whatsapp-patcher"
            if not self._clone_patcher(patcher_dir):
                return EngineResult(success=False, error="Failed to obtain WhatsApp patcher")

        req_file = patcher_dir / "requirements.txt"
        if req_file.exists():
            ctx.log("WhatsApp patcher: installing Python dependencies")
            try:
                subprocess.run(
                    [sys.executable, "-m", "pip", "install", "-q", "-r", str(req_file)],
                    capture_output=True,
                    text=True,
                    check=True,
                    timeout=120,
                )
            except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
                ctx.log("WhatsApp patcher: failed to install dependencies, continuing anyway")

        main_script = patcher_dir / "whatsapp_patcher" / "main.py"
        if not main_script.exists():
            main_script = patcher_dir / "main.py"
        if not main_script.exists():
            return EngineResult(success=False, error="WhatsApp patcher main.py not found")

        output_apk = ctx.output_dir / f"{ctx.current_apk.stem}.whatsapp-patched.apk"
        temp_dir = work_dir / "temp"
        temp_dir.mkdir(parents=True, exist_ok=True)

        cmd = [
            sys.executable,
            str(main_script),
            "-p",
            str(ctx.current_apk),
            "-o",
            str(output_apk),
            "--temp-path",
            str(temp_dir),
        ]
        if ab_tests:
            cmd.append("--ab-tests")

        ctx.log(f"WhatsApp patcher: running (timeout: {timeout}s)")
        try:
            subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=patcher_dir,
                timeout=timeout,
                check=True,
            )
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError, OSError) as e:
            return EngineResult(success=False, error=f"WhatsApp patcher failed: {e}")

        if not output_apk.exists():
            return EngineResult(success=False, error="WhatsApp patcher did not produce an output APK")

        ctx.log(f"WhatsApp patcher: complete → {output_apk}")
        return EngineResult(
            success=True,
            output_apk=output_apk,
            metadata={
                "features": WHATSAPP_FEATURES,
                "ab_tests_enabled": ab_tests,
            },
        )

    def _clone_patcher(self, patcher_dir: Path) -> bool:
        """Clone the WhatsApp patcher repository."""
        try:
            if patcher_dir.exists():
                shutil.rmtree(patcher_dir)
            subprocess.run(
                ["git", "clone", "--depth", "1", WHATSAPP_PATCHER_REPO, str(patcher_dir)],
                capture_output=True,
                text=True,
                check=True,
                timeout=120,
            )
            return True
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError):
            return False
