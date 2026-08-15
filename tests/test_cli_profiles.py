"""Tests for scripts/builder/cli_profiles.py."""

# ruff: noqa: S101

from __future__ import annotations

from pathlib import Path

from scripts.builder.cli_profiles import (
    ADOBO_CLI,
    BUILTIN_PROFILES,
    MORPHE_CLI,
    REVANCED_CLI_V5,
    REVANCED_CLI_V6,
    CLIProfileType,
    PatchCommandConfig,
    _detect_profile_from_help,
)


def test_builtin_profiles_include_adobo() -> None:
    assert CLIProfileType.ADOBO_CLI in BUILTIN_PROFILES
    assert BUILTIN_PROFILES[CLIProfileType.ADOBO_CLI] is ADOBO_CLI


def test_detect_adobo_profile_from_help() -> None:
    assert _detect_profile_from_help("Adobo CLI usage: ...") is ADOBO_CLI


def test_detect_morphe_profile_from_help() -> None:
    assert _detect_profile_from_help("Morphe CLI usage: ...") is MORPHE_CLI


def test_detect_v6_profile_from_help() -> None:
    assert _detect_profile_from_help("-b --patch-bundle <bundle>") is REVANCED_CLI_V6


def test_detect_v5_profile_default() -> None:
    assert _detect_profile_from_help("nothing helpful here") is REVANCED_CLI_V5


def test_v5_patch_args() -> None:
    """Verify ReVanced CLI v5 argument generation."""
    config = PatchCommandConfig(
        apk_path=Path("input.apk"),
        output_path=Path("output.apk"),
        patches_jars=[Path("patches.jar")],
        exclude=["patch1"],
        include=["patch2"],
        force=True,
        purge=True,
    )
    args = REVANCED_CLI_V5.build_patch_args(config)

    assert "--input" in args
    assert "input.apk" in args
    assert "--output" in args
    assert "output.apk" in args
    assert "--patch" in args
    assert "patches.jar" in args
    assert "--disable" in args
    assert "patch1" in args
    assert "--enable" in args
    assert "patch2" in args
    assert "--force" in args
    assert "--purge" in args


def test_v6_patch_args() -> None:
    """Verify ReVanced CLI v6 argument generation."""
    config = PatchCommandConfig(
        apk_path=Path("input.apk"),
        output_path=Path("output.apk"),
        patches_jars=[Path("patches.jar")],
        patches_post=[Path("post.jar")],
        exclude=["patch1"],
        include=["patch2"],
        merge=[Path("merge.jar")],
        keystore=Path("ks.keystore"),
        force=True,
        rip_lib=["lib1"],
        bare=True,
        inplace=True,
        werror=True,
    )
    args = REVANCED_CLI_V6.build_patch_args(config)

    assert "-i" in args
    assert "input.apk" in args
    assert "-o" in args
    assert "output.apk" in args
    assert "-e" in args
    assert "patches.jar" in args
    assert "-b" in args
    assert "post.jar" in args
    assert "-d" in args
    assert "patch1" in args
    assert "-m" in args
    assert "merge.jar" in args
    assert "-k" in args
    assert "ks.keystore" in args
    assert "-f" in args
    assert "-r" in args
    assert "lib1" in args
    assert "--bare" in args
    assert "--inplace" in args
    assert "-Werror" in args


def test_morphe_patch_args() -> None:
    """Verify Morphe CLI (morphe-desktop) argument generation.

    morphe-desktop's actual syntax (docs/documentation.md in
    MorpheApp/morphe-desktop): "patch" subcommand, input APK as a bare
    positional argument (no --input flag), -o/--out for output, -p/--patches
    for patch bundles.
    """
    config = PatchCommandConfig(
        apk_path=Path("input.apk"),
        output_path=Path("output.apk"),
        patches_jars=[Path("patches.jar")],
    )
    args = MORPHE_CLI.build_patch_args(config)

    assert args[0] == "patch"
    assert "input.apk" in args
    assert args[-1] == "input.apk"
    assert "--input" not in args
    assert "-o" in args
    assert "output.apk" in args
    assert "--output" not in args
    assert "-p" in args
    assert "patches.jar" in args
    assert "--patch" not in args


def test_list_patches_args() -> None:
    """Verify list-patches argument generation."""
    patches = [Path("p1.jar"), Path("p2.jar")]

    v5_args = REVANCED_CLI_V5.build_list_patches_args(patches)
    assert "--patches" in v5_args
    assert "p1.jar" in v5_args
    assert "p2.jar" in v5_args

    v6_args = REVANCED_CLI_V6.build_list_patches_args(patches)
    assert "-e" in v6_args
    assert "p1.jar" in v6_args
    assert "p2.jar" in v6_args

    morphe_args = MORPHE_CLI.build_list_patches_args(patches)
    assert "--patches" in morphe_args
    assert "p1.jar" in morphe_args
    assert "p2.jar" in morphe_args


def test_empty_config() -> None:
    """Verify argument generation with empty config still includes the "patch" subcommand keyword."""
    config = PatchCommandConfig()
    args = REVANCED_CLI_V6.build_patch_args(config)
    assert args == ["patch"]
