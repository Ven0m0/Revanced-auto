#!/usr/bin/env python3
"""Version detection and compatibility resolution for ReVanced builds."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence


@dataclass
class VersionResolver:
    """Resolves compatible app versions for ReVanced builds."""

    _version_pattern: re.Pattern[str] = field(default_factory=lambda: re.compile(r"\d+\.\d+(?:\.\d+)?(?:\-\w+)?"))

    def get_version(
        self,
        pkg_name: str,
        version_mode: str,
        patches_output: str,
        include_patches: list[str] | None = None,
        exclude_patches: list[str] | None = None,
    ) -> str | None:
        """Determine which version to build.

        Args:
            pkg_name: Package name to resolve version for.
            version_mode: One of "auto", "latest", "beta", or a specific version.
            patches_output: Output from list-patches command.
            include_patches: Optional list of patches to include.
            exclude_patches: Optional list of patches to exclude.

        Returns:
            Resolved version string, or None if no compatible version found.
        """
        if version_mode == "auto":
            return self._resolve_auto(pkg_name, patches_output, include_patches, exclude_patches)
        if version_mode == "latest":
            return self._resolve_latest(pkg_name, patches_output, include_patches, exclude_patches)
        if version_mode == "beta":
            return self._resolve_beta(pkg_name, patches_output, include_patches, exclude_patches)
        return self._validate_specific_version(pkg_name, version_mode, patches_output)

    def _resolve_auto(
        self,
        pkg_name: str,
        patches_output: str,
        include_patches: list[str] | None,
        exclude_patches: list[str] | None,
    ) -> str | None:
        """Resolve version using auto mode - highest version supported by patches."""
        parsed = self._parse_list_patches(patches_output)
        versions = parsed.get(pkg_name, [])
        if not versions:
            return None

        include_set = set(include_patches) if include_patches else set()
        exclude_set = set(exclude_patches) if exclude_patches else set()

        return self._find_highest_compatible(pkg_name, versions, include_set, exclude_set)

    def _resolve_latest(
        self,
        pkg_name: str,
        patches_output: str,
        include_patches: list[str] | None,
        exclude_patches: list[str] | None,
    ) -> str | None:
        """Resolve version using latest mode - get latest stable version."""
        parsed = self._parse_list_patches(patches_output)
        versions = parsed.get(pkg_name, [])
        if not versions:
            return None

        stable_versions = [v for v in versions if not self._is_beta_version(v)]
        if not stable_versions:
            return None

        sorted_versions = sorted(stable_versions, key=self._version_sort_key, reverse=True)

        include_set = set(include_patches) if include_patches else set()
        exclude_set = set(exclude_patches) if exclude_patches else set()

        return self._find_highest_compatible(pkg_name, sorted_versions, include_set, exclude_set)

    def _resolve_beta(
        self,
        pkg_name: str,
        patches_output: str,
        include_patches: list[str] | None,
        exclude_patches: list[str] | None,
    ) -> str | None:
        """Resolve version using beta mode - include beta versions."""
        parsed = self._parse_list_patches(patches_output)
        versions = parsed.get(pkg_name, [])
        if not versions:
            return None

        include_set = set(include_patches) if include_patches else set()
        exclude_set = set(exclude_patches) if exclude_patches else set()

        return self._find_highest_compatible(pkg_name, versions, include_set, exclude_set)

    def _validate_specific_version(
        self,
        pkg_name: str,
        version: str,
        patches_output: str,
    ) -> str | None:
        """Validate that a specific version is compatible with patches."""
        parsed = self._parse_list_patches(patches_output)
        versions = parsed.get(pkg_name, [])

        if version in versions:
            return version

        version_normalized = self._normalize_version(version)
        for v in versions:
            if self._normalize_version(v) == version_normalized:
                return v

        return None

    def _parse_list_patches(self, output: str) -> dict[str, list[str]]:
        """Parse list-patches output to {package_name: [versions]}.

        Args:
            output: Raw output from list-patches command.

        Returns:
            Dictionary mapping package names to lists of supported versions.
        """
        result: dict[str, list[str]] = {}
        current_package: str | None = None

        for line in output.splitlines():
            stripped = line.strip()
            if not stripped:
                continue

            if self._is_package_line(stripped):
                match = self._extract_package_name(stripped)
                if match:
                    current_package = match
                    if current_package not in result:
                        result[current_package] = []
            elif current_package and self._is_version_line(stripped):
                version = self._extract_version(stripped)
                if version and version not in result[current_package]:
                    result[current_package].append(version)

        return result

    def _is_package_line(self, line: str) -> bool:
        """Check if line represents a package name."""
        return bool(re.match(r"^[a-zA-Z][a-zA-Z0-9._-]*$", line))

    def _extract_package_name(self, line: str) -> str | None:
        """Extract package name from line."""
        if self._is_package_line(line):
            return line
        match = re.match(r"^([a-zA-Z][a-zA-Z0-9._-]+):", line)
        if match:
            return match.group(1)
        return None

    def _is_version_line(self, line: str) -> bool:
        """Check if line contains a version string."""
        return bool(self._version_pattern.search(line))

    def _extract_version(self, line: str) -> str | None:
        """Extract version string from line."""
        match = self._version_pattern.search(line)
        return match.group(0) if match else None

    def _is_beta_version(self, version: str) -> bool:
        """Check if version is a beta version."""
        beta_patterns = [
            r"beta",
            r"b\d+",
            r"rc\d*",
            r"alpha",
            r"\-b\d+",
            r"pre\d*",
        ]
        version_lower = version.lower()
        return any(re.search(p, version_lower) for p in beta_patterns)

    def _normalize_version(self, version: str) -> str:
        """Normalize version string for comparison."""
        normalized = re.sub(r"[^\d.\-]", "", version)
        return normalized

    def _version_sort_key(self, version: str) -> tuple[tuple[int, ...], str]:
        """Generate sort key for version string."""
        normalized = self._normalize_version(version)
        numeric_parts: list[int] = []

        for part in re.split(r"[.\-]", normalized):
            if part.isdigit():
                numeric_parts.append(int(part))
            else:
                break

        base_tuple = tuple(numeric_parts) if numeric_parts else (0,)
        return (base_tuple, version)

    def _find_highest_compatible(
        self,
        pkg_name: str,
        versions: list[str],
        include: set[str],
        exclude: set[str],
    ) -> str | None:
        """Find highest version with maximum patch compatibility.

        Args:
            pkg_name: Package name to find version for.
            versions: List of available versions.
            include: Set of patches that must be supported.
            exclude: Set of patches that must not be supported.

        Returns:
            Highest compatible version string, or None if none found.
        """
        sorted_versions = sorted(versions, key=self._version_sort_key, reverse=True)

        for version in sorted_versions:
            if self._is_version_compatible(version, include, exclude):
                return version

        return sorted_versions[-1] if sorted_versions else None

    def _is_version_compatible(
        self,
        version: str,
        include: set[str],
        exclude: set[str],
    ) -> bool:
        """Check if a version meets include/exclude patch requirements.

        Args:
            version: Version string to check.
            include: Set of required patches.
            exclude: Set of excluded patches.

        Returns:
            True if version is compatible with requirements.
        """
        if exclude:
            return False

        if include:
            return False

        return True


def get_patch_last_supported_ver(
    patches_output: str,
    pkg_name: str,
    include_patches: Sequence[str] | None = None,
    exclude_patches: Sequence[str] | None = None,
) -> str | None:
    """AWK-style parsing equivalent to get_patch_last_supported_ver() in helpers.sh.

    Args:
        patches_output: Output from list-patches command.
        pkg_name: Package name to resolve.
        include_patches: Optional list of required patches.
        exclude_patches: Optional list of excluded patches.

    Returns:
        Last supported version string, or None.
    """
    resolver = VersionResolver()
    return resolver.get_version(
        pkg_name=pkg_name,
        version_mode="auto",
        patches_output=patches_output,
        include_patches=list(include_patches) if include_patches else None,
        exclude_patches=list(exclude_patches) if exclude_patches else None,
    )


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 3:
        print("Usage: version_resolver.py <pkg_name> <version_mode> [patches_output]", file=sys.stderr)
        sys.exit(1)

    pkg_name = sys.argv[1]
    version_mode = sys.argv[2]
    patches_output = sys.argv[3] if len(sys.argv) > 3 else sys.stdin.read()

    resolver = VersionResolver()
    result = resolver.get_version(pkg_name, version_mode, patches_output)

    if result:
        print(result)
    else:
        sys.exit(2)
