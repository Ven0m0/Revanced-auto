#!/usr/bin/env python3
"""CLI argument compatibility profiles for different ReVanced CLI versions."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, TypedDict

from scripts.utils.java import JAVA_ARGS


class CLIProfileType(Enum):
    """ReVanced CLI profile types."""

    MORPHE_CLI = "morphe-cli"
    ADOBO_CLI = "adobo-cli"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class ArgMapping:
    """Argument mapping configuration."""

    flag: str
    requires_value: bool = True
    prepend_args: list[str] = field(default_factory=list)
    positional: bool = False
    """No flag at all -- the value is a bare positional argument (e.g. Morphe's input APK)."""
    join_with: str | None = None
    """Join all values into one flag with this separator instead of repeating the flag per value
    (e.g. Morphe's ``--striplibs arch1,arch2`` vs. classic CLI's repeated ``--rip-lib x --rip-lib y``)."""


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
    KEYSTORE_ALIAS: ArgMapping | None
    KEYSTORE_PASSWORD: ArgMapping | None
    KEYSTORE_ENTRY_PASSWORD: ArgMapping | None
    SIGNER: ArgMapping | None
    APK: ArgMapping | None
    OUTPUT: ArgMapping | None
    FORCE: ArgMapping | None
    RIP_LIB: ArgMapping | None
    MERGE: ArgMapping | None
    BARE: ArgMapping | None
    INPLACE: ArgMapping | None
    WERROR: ArgMapping | None
    PATCHES_POST: ArgMapping | None
    EXCLUSIVE: ArgMapping | None


def _list_patches_args_default() -> ListPatchesArgs:
    """Default list-patches arguments mapping."""
    return ListPatchesArgs()


def _patch_args_default() -> PatchArgs:
    """Default patch arguments mapping."""
    return PatchArgs()


@dataclass(frozen=True)
class PatchCommandConfig:
    """Configuration for the patch command.

    Attributes:
        apk_path: Path to input APK file.
        output_path: Path to output APK file.
        patches_jars: List of patch bundle JAR files.
        patches_post: List of post-patch bundle JAR files (v6+).
        exclude: List of patches to exclude.
        include: List of patches to include.
        merge: List of merge JAR files.
        keystore: Path to keystore file.
        keystore_alias: Alias of the key entry inside the keystore.
        keystore_password: Password for the keystore file itself.
        keystore_entry_password: Password for the keystore entry.
        signer: Signer name embedded in the APK signature.
        force: Force overwrite existing output.
        purge: Purge decompiled resources.
        rip_lib: List of libs to rip.
        bare: Bare APK mode.
        inplace: Inplace modification mode.
        werror: Treat warnings as errors.
        exclusive: Disable all patches except those explicitly enabled via ``include``.
        options: Additional options dict.
        patch_bundle: Patch name to owning bundle index.
    """

    apk_path: Path | None = None
    output_path: Path | None = None
    patches_jars: list[Path] = field(default_factory=list)
    patches_post: list[Path] = field(default_factory=list)
    exclude: list[str] = field(default_factory=list)
    include: list[str] = field(default_factory=list)
    merge: list[Path] = field(default_factory=list)
    keystore: Path | None = None
    keystore_alias: str | None = None
    keystore_password: str | None = None
    keystore_entry_password: str | None = None
    signer: str | None = None
    force: bool = False
    purge: bool = False
    rip_lib: list[str] = field(default_factory=list)
    bare: bool = False
    inplace: bool = False
    werror: bool = False
    exclusive: bool = False
    options: dict[str, dict[str, Any]] = field(default_factory=dict)
    """Per-patch option values: ``{patch_name: {option_key: value}}``. A ``None`` value emits
    the option flag with no value (sets it to null)."""
    patch_bundle: dict[str, int] = field(default_factory=dict)
    """Patch name -> index into ``patches_jars`` of the bundle that owns it. Unknown names go to the last bundle."""


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

    def build_patch_args(self, config: PatchCommandConfig) -> list[str]:
        """Build arguments for the patch command.

        Args:
            config: Patch command configuration.

        Returns:
            List of command arguments.
        """
        return build_cli_args(self, "patch", config)

    def build_list_patches_args(self, patches_jars: list[Path] | None = None) -> list[str]:
        """Build arguments for the list-patches command.

        Args:
            patches_jars: Optional list of patches JARs.

        Returns:
            List of command arguments.
        """
        config = PatchCommandConfig(patches_jars=patches_jars or [])
        return build_cli_args(self, "list-patches", config)


def _morphe_list_patches_args() -> ListPatchesArgs:
    """Morphe CLI (morphe-desktop) list-patches argument mappings.

    Source: https://raw.githubusercontent.com/MorpheApp/morphe-desktop/refs/heads/main/docs/documentation.md
    """
    return ListPatchesArgs(
        INDEX=ArgMapping(flag="-i", requires_value=False),
        PACKAGES=ArgMapping(flag="-p", requires_value=False),
        VERSIONS=ArgMapping(flag="-v", requires_value=False),
        OPTIONS=ArgMapping(flag="-o", requires_value=False),
        PATCHES=ArgMapping(flag="--patches", requires_value=True),
        UNIVERSAL=ArgMapping(flag="-u", requires_value=False),
    )


def _morphe_patch_args() -> PatchArgs:
    """Morphe CLI (morphe-desktop) patch argument mappings.

    Source: https://raw.githubusercontent.com/MorpheApp/morphe-desktop/refs/heads/main/docs/documentation.md

    morphe-desktop is a picocli app with a "patch" subcommand -- unlike
    classic ReVanced CLI, the input APK is a bare positional argument (no
    flag), and native-lib architectures to *keep* are one comma-joined
    --striplibs value rather than a repeated --rip-lib flag. PURGE/MERGE/
    BARE/INPLACE/WERROR have no morphe-desktop equivalent (its default is
    always to purge scratch files; --disable-purge is the inverse of PURGE,
    not modeled here since nothing currently sets that config field).
    """
    return PatchArgs(
        PATCHES=ArgMapping(flag="-p", requires_value=True),
        ENABLED=ArgMapping(flag="-e", requires_value=True),
        DISABLED=ArgMapping(flag="-d", requires_value=True),
        OPTIONS=ArgMapping(flag="-O", requires_value=True),
        PURGE=None,
        KEYSTORE=ArgMapping(flag="--keystore", requires_value=True),
        KEYSTORE_ALIAS=ArgMapping(flag="--keystore-entry-alias", requires_value=True),
        KEYSTORE_PASSWORD=ArgMapping(flag="--keystore-password", requires_value=True),
        KEYSTORE_ENTRY_PASSWORD=ArgMapping(flag="--keystore-entry-password", requires_value=True),
        SIGNER=ArgMapping(flag="--signer", requires_value=True),
        APK=ArgMapping(flag="", requires_value=True, positional=True),
        OUTPUT=ArgMapping(flag="-o", requires_value=True),
        FORCE=ArgMapping(flag="-f", requires_value=False),
        RIP_LIB=ArgMapping(flag="--striplibs", requires_value=True, join_with=","),
        MERGE=None,
        BARE=None,
        INPLACE=None,
        WERROR=None,
        PATCHES_POST=None,
        EXCLUSIVE=ArgMapping(flag="--exclusive", requires_value=False),
    )


MORPHE_CLI = CLIProfile(
    name="Morphe CLI",
    profile_type=CLIProfileType.MORPHE_CLI,
    list_patches_args=_morphe_list_patches_args(),
    patch_args=_morphe_patch_args(),
)

ADOBO_CLI = CLIProfile(
    name="Adobo (Morphe patches)",
    profile_type=CLIProfileType.ADOBO_CLI,
    list_patches_args=_morphe_list_patches_args(),
    patch_args=_morphe_patch_args(),
)

BUILTIN_PROFILES: dict[CLIProfileType, CLIProfile] = {
    CLIProfileType.MORPHE_CLI: MORPHE_CLI,
    CLIProfileType.ADOBO_CLI: ADOBO_CLI,
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
            ["java", *JAVA_ARGS, "-jar", str(cli_jar_path), "--help"],
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
    return ADOBO_CLI if "adobo" in help_output.lower() else MORPHE_CLI


def build_cli_args(
    profile: CLIProfile,
    command: str,
    config: PatchCommandConfig,
) -> list[str]:
    """Build command arguments from profile configuration.

    Args:
        profile: The CLI profile to use.
        command: The command to build args for ('list-patches' or 'patch').
        config: Patch command configuration.

    Returns:
        List of command arguments.
    """
    args: list[str] = [command]
    positional_args: list[str] = []

    if command == "patch":
        patch_args = profile.patch_args

        if config.apk_path:
            apk_mapping = patch_args.get("APK")
            if apk_mapping:
                if apk_mapping.positional:
                    positional_args.append(str(config.apk_path))
                else:
                    args.extend(apk_mapping.prepend_args)
                    args.append(apk_mapping.flag)
                    if apk_mapping.requires_value:
                        args.append(str(config.apk_path))

        if config.output_path:
            output_mapping = patch_args.get("OUTPUT")
            if output_mapping:
                args.extend(output_mapping.prepend_args)
                args.append(output_mapping.flag)
                if output_mapping.requires_value:
                    args.append(str(config.output_path))

        patches_mapping = patch_args.get("PATCHES")
        disabled_mapping = patch_args.get("DISABLED")
        enabled_mapping = patch_args.get("ENABLED")
        options_mapping = patch_args.get("OPTIONS")
        last_bundle = len(config.patches_jars) - 1
        # Options imply enabling their patch, except in exclusive mode where only ``include`` may be enabled.
        option_only = [] if config.exclusive else [n for n in config.options if n not in config.exclude]
        enable_names = dict.fromkeys([*config.include, *option_only])
        # Morphe applies -e/-d/-O to the most recent -p, so each selection must follow its own bundle.
        for idx, jar in enumerate(config.patches_jars):
            if patches_mapping:
                args.extend(patches_mapping.prepend_args)
                args.append(patches_mapping.flag)
                if patches_mapping.requires_value:
                    args.append(str(jar))
            if disabled_mapping:
                for patch_name in config.exclude:
                    if config.patch_bundle.get(patch_name, last_bundle) != idx:
                        continue
                    args.extend(disabled_mapping.prepend_args)
                    args.append(disabled_mapping.flag)
                    if disabled_mapping.requires_value:
                        args.append(patch_name)
            if enabled_mapping:
                for patch_name in enable_names:
                    if config.patch_bundle.get(patch_name, last_bundle) != idx:
                        continue
                    args.extend(enabled_mapping.prepend_args)
                    args.append(enabled_mapping.flag)
                    if enabled_mapping.requires_value:
                        args.append(patch_name)
                    # Morphe/Adobo's -O flag sets an option on whichever -e patch precedes it,
                    # so option flags must be emitted immediately after their patch's -e (see
                    # https://raw.githubusercontent.com/MorpheApp/morphe-desktop/refs/heads/main/docs/documentation.md).
                    if options_mapping:
                        for key, value in config.options.get(patch_name, {}).items():
                            args.append(options_mapping.flag)
                            args.append(key if value is None else f"{key}={value}")

        if config.patches_post:
            post_mapping = patch_args.get("PATCHES_POST")
            if post_mapping:
                for jar in config.patches_post:
                    args.extend(post_mapping.prepend_args)
                    args.append(post_mapping.flag)
                    if post_mapping.requires_value:
                        args.append(str(jar))

        if config.merge:
            merge_mapping = patch_args.get("MERGE")
            if merge_mapping:
                for jar in config.merge:
                    args.extend(merge_mapping.prepend_args)
                    args.append(merge_mapping.flag)
                    if merge_mapping.requires_value:
                        args.append(str(jar))

        if config.keystore:
            keystore_mapping = patch_args.get("KEYSTORE")
            if keystore_mapping:
                args.extend(keystore_mapping.prepend_args)
                args.append(keystore_mapping.flag)
                if keystore_mapping.requires_value:
                    args.append(str(config.keystore))

        if config.keystore_alias:
            alias_mapping = patch_args.get("KEYSTORE_ALIAS")
            if alias_mapping:
                args.extend(alias_mapping.prepend_args)
                args.append(alias_mapping.flag)
                if alias_mapping.requires_value:
                    args.append(config.keystore_alias)

        if config.keystore_password:
            ks_pass_mapping = patch_args.get("KEYSTORE_PASSWORD")
            if ks_pass_mapping:
                args.extend(ks_pass_mapping.prepend_args)
                args.append(ks_pass_mapping.flag)
                if ks_pass_mapping.requires_value:
                    args.append(config.keystore_password)

        if config.keystore_entry_password:
            entry_pass_mapping = patch_args.get("KEYSTORE_ENTRY_PASSWORD")
            if entry_pass_mapping:
                args.extend(entry_pass_mapping.prepend_args)
                args.append(entry_pass_mapping.flag)
                if entry_pass_mapping.requires_value:
                    args.append(config.keystore_entry_password)

        if config.signer:
            signer_mapping = patch_args.get("SIGNER")
            if signer_mapping:
                args.extend(signer_mapping.prepend_args)
                args.append(signer_mapping.flag)
                if signer_mapping.requires_value:
                    args.append(config.signer)

        if config.rip_lib:
            rip_mapping = patch_args.get("RIP_LIB")
            if rip_mapping:
                if rip_mapping.join_with is not None:
                    args.extend(rip_mapping.prepend_args)
                    args.append(rip_mapping.flag)
                    if rip_mapping.requires_value:
                        args.append(rip_mapping.join_with.join(config.rip_lib))
                else:
                    for lib in config.rip_lib:
                        args.extend(rip_mapping.prepend_args)
                        args.append(rip_mapping.flag)
                        if rip_mapping.requires_value:
                            args.append(lib)

        if config.force:
            force_mapping = patch_args.get("FORCE")
            if force_mapping:
                args.extend(force_mapping.prepend_args)
                args.append(force_mapping.flag)

        if config.purge:
            purge_mapping = patch_args.get("PURGE")
            if purge_mapping:
                args.extend(purge_mapping.prepend_args)
                args.append(purge_mapping.flag)

        if config.bare:
            bare_mapping = patch_args.get("BARE")
            if bare_mapping:
                args.extend(bare_mapping.prepend_args)
                args.append(bare_mapping.flag)

        if config.inplace:
            inplace_mapping = patch_args.get("INPLACE")
            if inplace_mapping:
                args.extend(inplace_mapping.prepend_args)
                args.append(inplace_mapping.flag)

        if config.werror:
            werror_mapping = patch_args.get("WERROR")
            if werror_mapping:
                args.extend(werror_mapping.prepend_args)
                args.append(werror_mapping.flag)

        if config.exclusive:
            exclusive_mapping = patch_args.get("EXCLUSIVE")
            if exclusive_mapping:
                args.extend(exclusive_mapping.prepend_args)
                args.append(exclusive_mapping.flag)

    elif command == "list-patches":
        list_patches_args = profile.list_patches_args

        if config.patches_jars:
            patches_mapping = list_patches_args.get("PATCHES")
            if patches_mapping:
                for jar in config.patches_jars:
                    args.extend(patches_mapping.prepend_args)
                    args.append(patches_mapping.flag)
                    if patches_mapping.requires_value:
                        args.append(str(jar))

    args.extend(positional_args)
    return args
