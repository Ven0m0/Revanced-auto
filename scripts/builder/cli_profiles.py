#!/usr/bin/env python3
"""CLI argument compatibility profiles for different ReVanced CLI versions."""

from __future__ import annotations

import re
import subprocess
import sys
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, TypedDict


class CLIProfileType(Enum):
    """ReVanced CLI profile types."""

    REVANCED_CLI_V5 = "revanced-cli-v5"
    REVANCED_CLI_V6 = "revanced-cli-v6"
    MORPHE_CLI = "morphe-cli"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class ArgMapping:
    """Argument mapping configuration."""

    flag: str
    requires_value: bool = True
    prepend_args: list[str] = field(default_factory=list)


class ListPatchesArgs(TypedDict, total=False):
    """Arguments for list-patches command."""

    INDEX: ArgMapping | None
    PACKAGES: ArgMapping | None
    VERSIONS: ArgMapping | None
    OPTIONS: ArgMapping | None
    PATCHES: ArgMapping | None
    UNIVERSAL: ArgMapping | None


class PatchArgs(TypedDict, total=False):
    """Arguments for patch command."""

    PATCHES: ArgMapping | None
    ENABLED: ArgMapping | None
    DISABLED: ArgMapping | None
    OPTIONS: ArgMapping | None
    PURGE: ArgMapping | None
    KEYSTORE: ArgMapping | None
    APK: ArgMapping | None
    OUTPUT: ArgMapping | None
    FORCE: ArgMapping | None
    RIP_LIB: ArgMapping | None
    MERGE: ArgMapping | None
    BARE: ArgMapping | None
    INPLACE: ArgMapping | None
    WERROR: ArgMapping | None
    PATCHES_POST: ArgMapping | None


def _list_patches_args_default() -> ListPatchesArgs:
    """Default list-patches arguments mapping."""
    return ListPatchesArgs()


def _patch_args_default() -> PatchArgs:
    """Default patch arguments mapping."""
    return PatchArgs()


@dataclass(frozen=True)
class CLIProfile:
    """CLI argument compatibility profile for different ReVanced CLI versions.

    Attributes:
        name: Human-readable profile name.
        profile_type: The CLI profile type enum.
        list_patches_args: Argument mappings for list-patches command.
        patch_args: Argument mappings for patch command.
    """

    name: str
    profile_type: CLIProfileType
    list_patches_args: ListPatchesArgs = field(default_factory=_list_patches_args_default)
    patch_args: PatchArgs = field(default_factory=_patch_args_default)


def _v5_list_patches_args() -> ListPatchesArgs:
    """ReVanced CLI v5 list-patches argument mappings."""
    return ListPatchesArgs(
        INDEX=ArgMapping(flag="--index", requires_value=True),
        PACKAGES=ArgMapping(flag="--packages", requires_value=True),
        VERSIONS=ArgMapping(flag="--versions", requires_value=True),
        OPTIONS=ArgMapping(flag="--options", requires_value=True),
        PATCHES=ArgMapping(flag="--patches", requires_value=True),
        UNIVERSAL=ArgMapping(flag="--universal", requires_value=False),
    )


def _v5_patch_args() -> PatchArgs:
    """ReVanced CLI v5 patch argument mappings."""
    return PatchArgs(
        PATCHES=ArgMapping(flag="--patch", requires_value=True),
        ENABLED=ArgMapping(flag="--enable", requires_value=True),
        DISABLED=ArgMapping(flag="--disable", requires_value=True),
        OPTIONS=ArgMapping(flag="--options", requires_value=True),
        PURGE=ArgMapping(flag="--purge", requires_value=False),
        KEYSTORE=ArgMapping(flag="--keystore", requires_value=True),
        APK=ArgMapping(flag="--input", requires_value=True),
        OUTPUT=ArgMapping(flag="--output", requires_value=True),
        FORCE=ArgMapping(flag="--force", requires_value=False),
        RIP_LIB=ArgMapping(flag="--rip-lib", requires_value=True),
        MERGE=ArgMapping(flag="--merge", requires_value=True),
    )


def _v6_list_patches_args() -> ListPatchesArgs:
    """ReVanced CLI v6 list-patches argument mappings."""
    return ListPatchesArgs(
        INDEX=ArgMapping(flag="-i", requires_value=True),
        PACKAGES=ArgMapping(flag="-p", requires_value=True),
        VERSIONS=ArgMapping(flag="-v", requires_value=True),
        OPTIONS=ArgMapping(flag="-o", requires_value=True),
        PATCHES=ArgMapping(flag="-e", requires_value=True),
        UNIVERSAL=ArgMapping(flag="-u", requires_value=False),
    )


def _v6_patch_args() -> PatchArgs:
    """ReVanced CLI v6 patch argument mappings."""
    return PatchArgs(
        PATCHES=ArgMapping(flag="-e", requires_value=True),
        ENABLED=ArgMapping(flag="-e", requires_value=True),
        DISABLED=ArgMapping(flag="-d", requires_value=True),
        OPTIONS=ArgMapping(flag="-o", requires_value=True),
        PURGE=ArgMapping(flag="--purge", requires_value=False),
        KEYSTORE=ArgMapping(flag="-k", requires_value=True),
        APK=ArgMapping(flag="-i", requires_value=True),
        OUTPUT=ArgMapping(flag="-o", requires_value=True),
        FORCE=ArgMapping(flag="-f", requires_value=False),
        RIP_LIB=ArgMapping(flag="-r", requires_value=True),
        MERGE=ArgMapping(flag="-m", requires_value=True),
        BARE=ArgMapping(flag="--bare", requires_value=False),
        INPLACE=ArgMapping(flag="--inplace", requires_value=False),
        WERROR=ArgMapping(flag="-Werror", requires_value=False),
        PATCHES_POST=ArgMapping(flag="-b", requires_value=True),
    )


def _morphe_list_patches_args() -> ListPatchesArgs:
    """Morphe CLI list-patches argument mappings."""
    return ListPatchesArgs(
        INDEX=ArgMapping(flag="--index", requires_value=True),
        PACKAGES=ArgMapping(flag="--package", requires_value=True),
        VERSIONS=ArgMapping(flag="--version", requires_value=True),
        OPTIONS=ArgMapping(flag="--options", requires_value=True),
        PATCHES=ArgMapping(flag="--patches", requires_value=True),
        UNIVERSAL=ArgMapping(flag="--universal", requires_value=False),
    )


def _morphe_patch_args() -> PatchArgs:
    """Morphe CLI patch argument mappings."""
    return PatchArgs(
        PATCHES=ArgMapping(flag="--patch", requires_value=True),
        ENABLED=ArgMapping(flag="--enable", requires_value=True),
        DISABLED=ArgMapping(flag="--disable", requires_value=True),
        OPTIONS=ArgMapping(flag="--options", requires_value=True),
        PURGE=ArgMapping(flag="--purge", requires_value=False),
        KEYSTORE=ArgMapping(flag="--keystore", requires_value=True),
        APK=ArgMapping(flag="--input", requires_value=True),
        OUTPUT=ArgMapping(flag="--output", requires_value=True),
        FORCE=ArgMapping(flag="--force", requires_value=False),
        RIP_LIB=ArgMapping(flag="--rip-lib", requires_value=True),
        MERGE=ArgMapping(flag="--merge", requires_value=True),
        BARE=ArgMapping(flag="--bare", requires_value=False),
        INPLACE=ArgMapping(flag="--inplace", requires_value=False),
        WERROR=ArgMapping(flag="--Werror", requires_value=False),
    )


REVANCED_CLI_V5 = CLIProfile(
    name="ReVanced CLI v5",
    profile_type=CLIProfileType.REVANCED_CLI_V5,
    list_patches_args=_v5_list_patches_args(),
    patch_args=_v5_patch_args(),
)

REVANCED_CLI_V6 = CLIProfile(
    name="ReVanced CLI v6",
    profile_type=CLIProfileType.REVANCED_CLI_V6,
    list_patches_args=_v6_list_patches_args(),
    patch_args=_v6_patch_args(),
)

MORPHE_CLI = CLIProfile(
    name="Morphe CLI",
    profile_type=CLIProfileType.MORPHE_CLI,
    list_patches_args=_morphe_list_patches_args(),
    patch_args=_morphe_patch_args(),
)

BUILTIN_PROFILES: dict[CLIProfileType, CLIProfile] = {
    CLIProfileType.REVANCED_CLI_V5: REVANCED_CLI_V5,
    CLIProfileType.REVANCED_CLI_V6: REVANCED_CLI_V6,
    CLIProfileType.MORPHE_CLI: MORPHE_CLI,
}


def detect_cli_profile(cli_jar_path: Path) -> CLIProfile:
    """Detect CLI profile by running --help on the CLI JAR.

    Args:
        cli_jar_path: Path to the CLI JAR file.

    Returns:
        Detected CLIProfile based on help output analysis.

    Raises:
        FileNotFoundError: If CLI JAR does not exist.
        subprocess.CalledProcessError: If --help command fails.
    """
    if not cli_jar_path.exists():
        raise FileNotFoundError(f"CLI JAR not found: {cli_jar_path}")

    try:
        result = subprocess.run(
            [sys.executable, "-m", "revanced", "--help"],
            capture_output=True,
            text=True,
            check=True,
            timeout=30,
        )
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        try:
            result = subprocess.run(
                ["java", "-jar", str(cli_jar_path), "--help"],
                capture_output=True,
                text=True,
                check=True,
                timeout=30,
            )
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
            raise RuntimeError(f"Failed to run --help on CLI JAR: {e}") from e

    help_output = result.stdout + result.stderr
    return _detect_profile_from_help(help_output)


def _detect_profile_from_help(help_output: str) -> CLIProfile:
    """Detect profile type from help output text.

    Args:
        help_output: The --help command output.

    Returns:
        Detected CLIProfile.
    """
    help_lower = help_output.lower()

    if "morphe" in help_lower:
        return MORPHE_CLI

    if re.search(r"-b\s+--patch-bundle", help_output) or re.search(r"--patch-bundle\s+\[", help_output):
        return REVANCED_CLI_V6

    if re.search(r"--patches\s+<", help_output) and "-p" not in help_output:
        return REVANCED_CLI_V5

    if re.search(r"-p\s+--packages", help_output) or re.search(r"-e\s+--patch", help_output):
        return REVANCED_CLI_V6

    return REVANCED_CLI_V5


def build_cli_args(
    profile: CLIProfile,
    command: str,
    patches_jars: list[Path] | None = None,
    patches_post: list[Path] | None = None,
    exclude: list[str] | None = None,
    include: list[str] | None = None,
    merge: list[Path] | None = None,
    keystore: Path | None = None,
    apk_path: Path | None = None,
    output_path: Path | None = None,
    force: bool = False,
    purge: bool = False,
    rip_lib: list[str] | None = None,
    bare: bool = False,
    inplace: bool = False,
    werror: bool = False,
    _options: dict[str, Any] | None = None,
) -> list[str]:
    """Build command arguments from profile configuration.

    Args:
        profile: The CLI profile to use.
        command: The command to build args for ('list-patches' or 'patch').
        patches_jars: List of patch bundle JAR files.
        patches_post: List of post-patch bundle JAR files (v6+).
        exclude: List of patches to exclude.
        include: List of patches to include (exclusive with exclude).
        merge: List of merge JAR files.
        keystore: Path to keystore file.
        apk_path: Path to input APK file.
        output_path: Path to output APK file.
        force: Force overwrite existing output.
        purge: Purge decompiled resources.
        rip_lib: List of libs to rip.
        bare: Bare APK mode.
        inplace: Inplace modification mode.
        werror: Treat warnings as errors.
        options: Additional options dict.

    Returns:
        List of command arguments.
    """
    args: list[str] = []
    patch_args = profile.patch_args

    if command == "patch":
        if apk_path:
            apk_mapping = patch_args.get("APK")
            if apk_mapping:
                args.extend(apk_mapping.prepend_args)
                args.append(apk_mapping.flag)
                if apk_mapping.requires_value:
                    args.append(str(apk_path))

        if output_path:
            output_mapping = patch_args.get("OUTPUT")
            if output_mapping:
                args.extend(output_mapping.prepend_args)
                args.append(output_mapping.flag)
                if output_mapping.requires_value:
                    args.append(str(output_path))

        if patches_jars:
            patches_mapping = patch_args.get("PATCHES")
            if patches_mapping:
                for jar in patches_jars:
                    args.extend(patches_mapping.prepend_args)
                    args.append(patches_mapping.flag)
                    if patches_mapping.requires_value:
                        args.append(str(jar))

        if patches_post:
            post_mapping = patch_args.get("PATCHES_POST")
            if post_mapping:
                for jar in patches_post:
                    args.extend(post_mapping.prepend_args)
                    args.append(post_mapping.flag)
                    if post_mapping.requires_value:
                        args.append(str(jar))

        if exclude:
            disabled_mapping = patch_args.get("DISABLED")
            if disabled_mapping:
                for patch_name in exclude:
                    args.extend(disabled_mapping.prepend_args)
                    args.append(disabled_mapping.flag)
                    if disabled_mapping.requires_value:
                        args.append(patch_name)

        if include:
            enabled_mapping = patch_args.get("ENABLED")
            if enabled_mapping:
                for patch_name in include:
                    args.extend(enabled_mapping.prepend_args)
                    args.append(enabled_mapping.flag)
                    if enabled_mapping.requires_value:
                        args.append(patch_name)

        if merge:
            merge_mapping = patch_args.get("MERGE")
            if merge_mapping:
                for jar in merge:
                    args.extend(merge_mapping.prepend_args)
                    args.append(merge_mapping.flag)
                    if merge_mapping.requires_value:
                        args.append(str(jar))

        if keystore:
            keystore_mapping = patch_args.get("KEYSTORE")
            if keystore_mapping:
                args.extend(keystore_mapping.prepend_args)
                args.append(keystore_mapping.flag)
                if keystore_mapping.requires_value:
                    args.append(str(keystore))

        if rip_lib:
            rip_mapping = patch_args.get("RIP_LIB")
            if rip_mapping:
                for lib in rip_lib:
                    args.extend(rip_mapping.prepend_args)
                    args.append(rip_mapping.flag)
                    if rip_mapping.requires_value:
                        args.append(lib)

        if force:
            force_mapping = patch_args.get("FORCE")
            if force_mapping:
                args.extend(force_mapping.prepend_args)
                args.append(force_mapping.flag)

        if purge:
            purge_mapping = patch_args.get("PURGE")
            if purge_mapping:
                args.extend(purge_mapping.prepend_args)
                args.append(purge_mapping.flag)

        if bare:
            bare_mapping = patch_args.get("BARE")
            if bare_mapping:
                args.extend(bare_mapping.prepend_args)
                args.append(bare_mapping.flag)

        if inplace:
            inplace_mapping = patch_args.get("INPLACE")
            if inplace_mapping:
                args.extend(inplace_mapping.prepend_args)
                args.append(inplace_mapping.flag)

        if werror:
            werror_mapping = patch_args.get("WERROR")
            if werror_mapping:
                args.extend(werror_mapping.prepend_args)
                args.append(werror_mapping.flag)

    elif command == "list-patches":
        list_patches_args = profile.list_patches_args

        if patches_jars:
            patches_mapping = list_patches_args.get("PATCHES")
            if patches_mapping:
                for jar in patches_jars:
                    args.extend(patches_mapping.prepend_args)
                    args.append(patches_mapping.flag)
                    if patches_mapping.requires_value:
                        args.append(str(jar))

    return args


@dataclass
class BuildPatchKwargs:
    """Keyword arguments for CLIProfile.build_patch_args method."""

    apk_path: Path
    output_path: Path
    patches_jars: list[Path] = field(default_factory=list)
    exclude: list[str] = field(default_factory=list)
    include: list[str] = field(default_factory=list)
    merge: list[Path] = field(default_factory=list)
    keystore: Path | None = None
    force: bool = False
    purge: bool = False
    rip_lib: list[str] = field(default_factory=list)
    bare: bool = False
    inplace: bool = False
    werror: bool = False
    patches_post: list[Path] = field(default_factory=list)
    options: dict[str, Any] = field(default_factory=dict)


CLIProfile.build_patch_args = lambda self, **kwargs: build_cli_args(  # type: ignore[attr-defined,method-assign]
    profile=self,
    command="patch",
    patches_jars=kwargs.get("patches_jars"),
    patches_post=kwargs.get("patches_post"),
    exclude=kwargs.get("exclude"),
    include=kwargs.get("include"),
    merge=kwargs.get("merge"),
    keystore=kwargs.get("keystore"),
    apk_path=kwargs.get("apk_path"),
    output_path=kwargs.get("output_path"),
    force=kwargs.get("force", False),
    purge=kwargs.get("purge", False),
    rip_lib=kwargs.get("rip_lib"),
    bare=kwargs.get("bare", False),
    inplace=kwargs.get("inplace", False),
    werror=kwargs.get("werror", False),
    options=kwargs.get("options"),
)


CLIProfile.build_list_patches_args = lambda self, patches_jars=None: build_cli_args(  # type: ignore[attr-defined,method-assign]
    profile=self,
    command="list-patches",
    patches_jars=patches_jars,
)
