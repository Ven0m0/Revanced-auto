#!/usr/bin/env python3
"""Magisk and KernelSU module generator for patched APKs."""

from __future__ import annotations

import shutil
import zipfile
from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path
import tempfile


class ModuleType(Enum):
    """Supported module types."""

    MAGISK = auto()
    KERNSU = auto()


@dataclass
class ModuleMetadata:
    """Metadata for the module."""

    app_name: str
    brand: str
    version: str
    version_code: str
    author: str = "ReVanced/RVX Builder"
    description: str = "Patched APK module"


class ModuleGenerator:
    """Generates Magisk and KernelSU modules from patched APKs."""

    def __init__(self, module_type: ModuleType = ModuleType.MAGISK):
        """Initialize the module generator.

        Args:
            module_type: The type of module to generate (MAGISK or KERNSU).
        """
        self.module_type = module_type

    def generate(
        self,
        apk_path: Path,
        app_name: str,
        brand: str,
        version: str,
        output_dir: Path | None = None,
    ) -> Path:
        """Generate module ZIP.

        Args:
            apk_path: Path to the patched APK file.
            app_name: Name of the application.
            brand: Brand/version identifier.
            version: Module version string.
            output_dir: Optional output directory. Defaults to current directory.

        Returns:
            Path to the generated module ZIP file.
        """
        apk_path = Path(apk_path)
        if not apk_path.exists():
            raise FileNotFoundError(f"APK not found: {apk_path}")

        metadata = ModuleMetadata(
            app_name=app_name,
            brand=brand,
            version=version,
            version_code=self._version_to_code(version),
        )

        with self._create_structure(apk_path) as temp_dir:
            temp_path = Path(temp_dir)
            self._write_module_files(temp_path, apk_path, metadata)
            output_path = self._create_zip(temp_path, app_name, output_dir)

        return output_path

    def _create_structure(self, apk_path: Path) -> tempfile.TemporaryDirectory:
        """Create module directory structure.

        Args:
            apk_path: Path to the APK file.

        Returns:
            TemporaryDirectory containing the module structure.
        """
        temp_dir = tempfile.mkdtemp(prefix="module_")
        temp_path = Path(temp_dir)

        meta_inf = temp_path / "META-INF" / "com" / "google" / "android"
        meta_inf.mkdir(parents=True, exist_ok=True)

        system_app = temp_path / "system" / "app" / apk_path.stem
        system_app.mkdir(parents=True, exist_ok=True)

        return tempfile.TemporaryDirectory(prefix="module_")

    def _write_module_files(
        self,
        temp_path: Path,
        apk_path: Path,
        metadata: ModuleMetadata,
    ) -> None:
        """Write all module files to the temporary directory.

        Args:
            temp_path: Path to the temporary module directory.
            apk_path: Path to the source APK file.
            metadata: Module metadata.
        """
        meta_inf = temp_path / "META-INF" / "com" / "google" / "android"
        system_app = temp_path / "system" / "app" / apk_path.stem

        shutil.copy2(apk_path, system_app / apk_path.name)

        module_prop = self._generate_module_prop(metadata)
        (temp_path / "module.prop").write_text(module_prop, encoding="utf-8")

        service_sh = self._generate_service_sh(apk_path)
        (temp_path / "service.sh").write_text(service_sh, encoding="utf-8")

        updater_script = self._generate_update_script()
        (meta_inf / "updater-script").write_text(updater_script, encoding="utf-8")

        if self.module_type == ModuleType.KERNSU:
            ksu_config = self._generate_ksu_config()
            (temp_path / "ksu_allow_su").write_text(ksu_config, encoding="utf-8")

            system_prop = self._generate_system_prop(metadata)
            (temp_path / "system.prop").write_text(system_prop, encoding="utf-8")

    def _generate_module_prop(self, metadata: ModuleMetadata) -> str:
        """Generate module.prop content.

        Args:
            metadata: Module metadata.

        Returns:
            Content of module.prop file.
        """
        module_id = f"rvmm.{metadata.brand.lower()}.{metadata.app_name.lower()}"
        module_name = f"{metadata.app_name} ({metadata.brand})"

        lines = [
            f"id={module_id}",
            f"name={module_name}",
            f"version={metadata.version}",
            f"versionCode={metadata.version_code}",
            f"author={metadata.author}",
            f"description={metadata.description}",
        ]
        return "\n".join(lines) + "\n"

    def _generate_service_sh(self, apk_path: Path) -> str:
        """Generate service.sh for APK mounting.

        Args:
            apk_path: Path to the APK file.

        Returns:
            Content of service.sh file.
        """
        app_name = apk_path.stem
        apk_name = apk_path.name

        lines = [
            "#!/system/bin/sh",
            "",
            "MODDIR=${0%/*}",
            "",
            f"APK_DIR=\"$MODDIR/system/app/{app_name}\"",
            f"APK_PATH=\"$APK_DIR/{apk_name}\"",
            "",
            "# Ensure APK directory exists",
            "[ -f \"$APK_PATH\" ] || exit 1",
            "",
            "# Try rvmm-zygisk-mount first for better compatibility",
            "if [ -f \"$MODDIR/rvmm-zygisk-mount\" ]; then",
            "    mv \"$MODDIR/rvmm-zygisk-mount\" \"$APK_DIR/rvmm-zygisk-mount\"",
            "    chmod 644 \"$APK_DIR/rvmm-zygisk-mount\"",
            "fi",
            "",
            "# Set permissions",
            "chmod 644 \"$APK_PATH\"",
            "",
            "# For Zygisk-based mounting (Magisk)",
        ]

        if self.module_type == ModuleType.MAGISK:
            lines.extend([
                "",
                "# Check if ZYSK is available for mounting",
                "if [ -x \"$MODDIRZYSK\" ] || [ -x \"$MODDIR/zygiskZYSK\" ]; then",
                "    ZYSK=\"$MODDIRZYSK\"",
                "    [ -x \"$MODDIR/zygiskZYSK\" ] && ZYSK=\"$MODDIR/zygiskZYSK\"",
                "    \"$ZYSK\" mount \"$APK_PATH\"",
                "fi",
            ])
        elif self.module_type == ModuleType.KERNSU:
            lines.extend([
                "",
                "# KernelSU handles APK mounting natively",
                "# Additional KernelSU-specific logic can be added here",
            ])

        return "\n".join(lines) + "\n"

    def _generate_update_script(self) -> str:
        """Generate updater-script for installation.

        Returns:
            Content of updater-script file.
        """
        lines = [
            "#MAGISK",
            "",
            "if [ -f \"/data/adb/RVMM-MAGISK/migrate.sh\" ]; then",
            "    sh /data/adb/RVMM-MAGISK/migrate.sh",
            "fi",
            "",
            "mount_all() {",
            "    sys_app_mounted=false",
            "    if [ \"$(getprop sys.checkfs)\" != \"true\" ]; then",
            "        mount_all /system",
            "        sys_app_mounted=true",
            "    fi",
            "}",
            "",
            "REPLACE=\"/system/app/*\"",
            "",
            "mkdir /system/app",
            "cp -a /data/adb/modules/$MODNAME/system/app/* /system/app/ 2>/dev/null || true",
            "",
            "touch /data/adb/modules/$MODNAME/auto_mount",
        ]

        if self.module_type == ModuleType.KERNSU:
            lines.extend([
                "",
                "# KernelSU specific",
                "touch /data/adb/ksu/$MODNAME/auto_mount",
            ])

        return "\n".join(lines) + "\n"

    def _generate_ksu_config(self) -> str:
        """Generate KernelSU allow_su configuration.

        Returns:
            Content of ksu_allow_su file.
        """
        lines = [
            "# KernelSU module configuration",
            "",
            "# Allow su for this module",
            "allow_su=true",
            "",
            "# Mount strategy",
            "mount_mode=auto",
        ]
        return "\n".join(lines) + "\n"

    def _generate_system_prop(self, metadata: ModuleMetadata) -> str:
        """Generate system.prop additions for KernelSU.

        Args:
            metadata: Module metadata.

        Returns:
            Content of system.prop file.
        """
        lines = [
            "# System properties for patched APK",
            "",
            f"# {metadata.app_name} ({metadata.brand})",
            f"persist.{metadata.brand.lower()}.{metadata.app_name.lower()}.version={metadata.version}",
        ]
        return "\n".join(lines) + "\n"

    def _create_zip(
        self,
        temp_path: Path,
        app_name: str,
        output_dir: Path | None = None,
    ) -> Path:
        """Create the module ZIP file.

        Args:
            temp_path: Path to the temporary module directory.
            app_name: Name of the application.
            output_dir: Optional output directory.

        Returns:
            Path to the created ZIP file.
        """
        if output_dir is None:
            output_dir = Path.cwd()
        else:
            output_dir = Path(output_dir)
            output_dir.mkdir(parents=True, exist_ok=True)

        zip_name = f"{app_name.lower()}_{self.module_type.name.lower()}_module.zip"
        zip_path = output_dir / zip_name

        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for file_path in temp_path.rglob("*"):
                if file_path.is_file():
                    arcname = file_path.relative_to(temp_path)
                    zf.write(file_path, arcname)

        return zip_path

    @staticmethod
    def _version_to_code(version: str) -> str:
        """Convert version string to version code.

        Args:
            version: Version string (e.g., "1.2.3").

        Returns:
            Numeric version code.
        """
        parts = version.split(".")
        if len(parts) >= 3:
            try:
                major = int(parts[0]) * 10000
                minor = int(parts[1]) * 100
                patch = int(parts[2]) if len(parts) > 2 else 0
                return str(major + minor + patch)
            except ValueError:
                pass
        return "1000"
