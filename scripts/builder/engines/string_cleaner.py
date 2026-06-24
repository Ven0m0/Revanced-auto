"""String cleaner engine for removing unused Android string resources.

Ported from apk-tweak's string_cleaner engine.
Decompiles the APK with apktool, analyzes string usage, optionally removes
unused string definitions, then recompiles and zipaligns the result.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import NamedTuple

from scripts.builder.engines import EngineContext, EngineResult, EngineStage
from scripts.utils.apk import align_apk

# Pre-compiled regex patterns.
_STRING_DEF_PATTERN = re.compile(r'<string\s+name="([^"]+)"')
_R_STRING_PATTERN = re.compile(r"R\.string\.([a-zA-Z0-9_]+)")
_XML_STRING_PATTERN = re.compile(r"@string/([a-zA-Z0-9_]+)")
_XML_CLEANUP_PATTERN = re.compile(
    r'^\s*<string\s+name="([^"]+)"[^>]*>.*?</string>[ \t]*\n?',
    re.MULTILINE | re.DOTALL,
)


class StringUsage(NamedTuple):
    """String resource usage information."""

    name: str
    is_used: bool
    locations: list[str]


class StringCleanerEngine:
    """Engine that removes unused Android string resources."""

    name = "string_cleaner"
    stage = EngineStage.POST_PATCH

    def run(self, ctx: EngineContext) -> EngineResult:
        """Run the string cleaner engine.

        Args:
            ctx: Engine context.

        Returns:
            EngineResult with the cleaned APK path.
        """
        options = ctx.app_options.get(self.name, {})
        clean_strings = bool(options.get("clean_unused_strings", False))
        remove_strings = bool(options.get("remove_unused_strings", False))
        apktool_path = str(options.get("apktool_path", "apktool"))

        if not clean_strings:
            ctx.log("String cleaner: disabled")
            return EngineResult(success=True, output_apk=ctx.current_apk)

        if not shutil.which(apktool_path):
            ctx.log(
                f"String cleaner: apktool not found at '{apktool_path}', skipping",
                level=40,
            )
            return EngineResult(success=True, output_apk=ctx.current_apk)

        work_dir = ctx.work_dir / self.name
        work_dir.mkdir(parents=True, exist_ok=True)
        decompiled_dir = work_dir / "decompiled"

        ctx.log(f"String cleaner: decompiling {ctx.current_apk.name}")
        if not self._decompile_apk(ctx.current_apk, decompiled_dir, apktool_path):
            return EngineResult(success=False, error="Failed to decompile APK")

        usage_map = self._analyze_apk_strings(decompiled_dir, ctx)
        if not usage_map:
            return EngineResult(success=False, error="No strings found or analysis failed")

        unused_strings = [name for name, usage in usage_map.items() if not usage.is_used]
        metadata = {
            "total_strings": len(usage_map),
            "unused_strings": len(unused_strings),
        }

        if unused_strings:
            ctx.log(f"String cleaner: found {len(unused_strings)} unused strings")
            if remove_strings:
                self._remove_unused_strings(decompiled_dir, usage_map, ctx)

        recompiled_apk = work_dir / f"{ctx.current_apk.stem}-recompiled.apk"
        ctx.log(f"String cleaner: recompiling to {recompiled_apk.name}")
        if not self._recompile_apk(decompiled_dir, recompiled_apk, apktool_path):
            return EngineResult(success=False, error="Failed to recompile APK")

        output_apk = ctx.output_dir / f"{ctx.current_apk.stem}.strings.apk"
        if not align_apk(recompiled_apk, output_apk):
            ctx.log("String cleaner: zipalign failed, using recompiled APK")
            output_apk = recompiled_apk

        ctx.log(
            f"String cleaner: done (total={metadata['total_strings']}, "
            f"unused={metadata['unused_strings']}, removed={remove_strings})"
        )

        return EngineResult(success=True, output_apk=output_apk, metadata=metadata)

    def _decompile_apk(self, apk: Path, output_dir: Path, apktool_path: str) -> bool:
        """Decompile APK using apktool."""
        try:
            if output_dir.exists():
                shutil.rmtree(output_dir)
            subprocess.run(
                [apktool_path, "d", "-f", "-o", str(output_dir), str(apk)],
                capture_output=True,
                text=True,
                check=True,
                timeout=300,
            )
            return True
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError):
            return False

    def _recompile_apk(self, input_dir: Path, output_apk: Path, apktool_path: str) -> bool:
        """Recompile APK using apktool."""
        try:
            subprocess.run(
                [apktool_path, "b", "-o", str(output_apk), str(input_dir)],
                capture_output=True,
                text=True,
                check=True,
                timeout=300,
            )
            return output_apk.exists()
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError):
            return False

    def _extract_string_names(self, xml_content: str) -> set[str]:
        """Extract string resource names from strings.xml content."""
        return {match.group(1) for match in _STRING_DEF_PATTERN.finditer(xml_content)}

    def _find_string_references(self, content: str) -> set[str]:
        """Find string resource references in file content."""
        references: set[str] = set()
        references.update(match.group(1) for match in _R_STRING_PATTERN.finditer(content))
        references.update(match.group(1) for match in _XML_STRING_PATTERN.finditer(content))
        return references

    def _analyze_apk_strings(
        self,
        decompiled_dir: Path,
        ctx: EngineContext,
    ) -> dict[str, StringUsage]:
        """Analyze decompiled APK for string usage."""
        all_strings: set[str] = set()
        used_strings: set[str] = set()
        string_locations: dict[str, list[str]] = {}
        reserved = {"app_name", "app_name_suffixed"}

        strings_files: list[Path] = []
        source_files: list[Path] = []

        for root, dirs, files in os.walk(decompiled_dir, topdown=True):
            root_path = Path(root)
            if root_path != decompiled_dir and "drawable" in root_path.name:
                dirs[:] = []
                continue
            for file in files:
                if file == "strings.xml":
                    strings_files.append(root_path / file)
                elif file.endswith((".xml", ".smali")):
                    source_files.append(root_path / file)

        for strings_file in strings_files:
            try:
                content = strings_file.read_text(encoding="utf-8", errors="ignore")
                file_strings = self._extract_string_names(content)
                all_strings.update(file_strings)
                rel_path = str(strings_file.relative_to(decompiled_dir))
                for string_name in file_strings:
                    string_locations.setdefault(string_name, []).append(rel_path)
            except (OSError, UnicodeDecodeError) as e:
                ctx.log(f"String cleaner: error reading {strings_file.name}: {e}")

        for source_file in source_files:
            try:
                content = source_file.read_text(encoding="utf-8", errors="ignore")
                used_strings.update(self._find_string_references(content))
            except (OSError, UnicodeDecodeError):
                pass

        used_strings.update(reserved)

        usage_map: dict[str, StringUsage] = {}
        for string_name in all_strings:
            is_used = string_name in used_strings
            usage_map[string_name] = StringUsage(
                name=string_name,
                is_used=is_used,
                locations=string_locations.get(string_name, []),
            )

        return usage_map

    def _clean_xml_content(self, content: str, unused_strings: set[str]) -> str:
        """Remove unused string definitions from XML content."""

        def replacer(match: re.Match[str]) -> str:
            name = match.group(1)
            if name in unused_strings:
                return ""
            return match.group(0)

        return _XML_CLEANUP_PATTERN.sub(replacer, content)

    def _remove_unused_strings(
        self,
        decompiled_dir: Path,
        usage_map: dict[str, StringUsage],
        ctx: EngineContext,
    ) -> None:
        """Remove unused strings from XML files."""
        unused_strings = {name for name, usage in usage_map.items() if not usage.is_used}
        if not unused_strings:
            return

        all_locations: set[str] = set()
        for string_name in unused_strings:
            all_locations.update(usage_map[string_name].locations)

        for rel_path in all_locations:
            file_path = decompiled_dir / rel_path
            if not file_path.exists():
                continue
            try:
                content = file_path.read_text(encoding="utf-8", errors="ignore")
                original_lines = len(content.splitlines())
                content = self._clean_xml_content(content, unused_strings)
                removed_lines = original_lines - len(content.splitlines())
                if removed_lines > 0:
                    file_path.write_text(content, encoding="utf-8")
                    ctx.log(f"String cleaner: cleaned {rel_path} (removed {removed_lines} lines)")
            except (OSError, UnicodeError) as e:
                ctx.log(f"String cleaner: error processing {rel_path}: {e}")
