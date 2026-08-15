#!/usr/bin/env python3
"""Magisk and KernelSU module generator for patched APKs."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum, auto
from pathlib import Path

logger = logging.getLogger(__name__)


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
            f'APK_DIR="$MODDIR/system/app/{app_name}"',
            f'APK_PATH="$APK_DIR/{apk_name}"',
            "",
            "# Ensure APK directory exists",
            '[ -f "$APK_PATH" ] || exit 1',
            "",
            "# Try rvmm-zygisk-mount first for better compatibility",
            'if [ -f "$MODDIR/rvmm-zygisk-mount" ]; then',
            '    mv "$MODDIR/rvmm-zygisk-mount" "$APK_DIR/rvmm-zygisk-mount"',
            '    chmod 644 "$APK_DIR/rvmm-zygisk-mount"',
            "fi",
            "",
            "# Set permissions",
            'chmod 644 "$APK_PATH"',
            "",
            "# For Zygisk-based mounting (Magisk)",
        ]

        if self.module_type == ModuleType.MAGISK:
            lines.extend(
                [
                    "",
                    "# Check if ZYSK is available for mounting",
                    'if [ -x "$MODDIRZYSK" ] || [ -x "$MODDIR/zygiskZYSK" ]; then',
                    '    ZYSK="$MODDIRZYSK"',
                    '    [ -x "$MODDIR/zygiskZYSK" ] && ZYSK="$MODDIR/zygiskZYSK"',
                    '    "$ZYSK" mount "$APK_PATH"',
                    "fi",
                ]
            )
        elif self.module_type == ModuleType.KERNSU:
            lines.extend(
                [
                    "",
                    "# KernelSU handles APK mounting natively",
                    "# Additional KernelSU-specific logic can be added here",
                ]
            )

        return "\n".join(lines) + "\n"

    def _generate_update_script(self) -> str:
        """Generate updater-script for installation.

        Returns:
            Content of updater-script file.
        """
        lines = [
            "#MAGISK",
            "",
            'if [ -f "/data/adb/RVMM-MAGISK/migrate.sh" ]; then',
            "    sh /data/adb/RVMM-MAGISK/migrate.sh",
            "fi",
            "",
            "mount_all() {",
            "    sys_app_mounted=false",
            '    if [ "$(getprop sys.checkfs)" != "true" ]; then',
            "        mount_all /system",
            "        sys_app_mounted=true",
            "    fi",
            "}",
            "",
            'REPLACE="/system/app/*"',
            "",
            "mkdir /system/app",
            "cp -a /data/adb/modules/$MODNAME/system/app/* /system/app/ 2>/dev/null || true",
            "",
            "touch /data/adb/modules/$MODNAME/auto_mount",
        ]

        if self.module_type == ModuleType.KERNSU:
            lines.extend(
                [
                    "",
                    "# KernelSU specific",
                    "touch /data/adb/ksu/$MODNAME/auto_mount",
                ]
            )

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
