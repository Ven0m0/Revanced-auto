"""Tests for scripts/builder/cli_profiles.py."""

# ruff: noqa: S101

from __future__ import annotations

from pathlib import Path

from scripts.builder.cli_profiles import (
    ADOBO_CLI,
    BUILTIN_PROFILES,
    MORPHE_CLI,
    CLIProfileType,
    PatchCommandConfig,
    _detect_profile_from_help,
)


def test_builtin_profiles_include_adobo() -> None:
    assert CLIProfileType.ADOBO_CLI in BUILTIN_PROFILES
    assert BUILTIN_PROFILES[CLIProfileType.ADOBO_CLI] is ADOBO_CLI


def test_builtin_profiles_are_morphe_family_only() -> None:
    assert set(BUILTIN_PROFILES) == {CLIProfileType.MORPHE_CLI, CLIProfileType.ADOBO_CLI}


def test_detect_adobo_profile_from_help() -> None:
    assert _detect_profile_from_help("Adobo CLI usage: ...") is ADOBO_CLI


def test_detect_morphe_profile_from_help() -> None:
    assert _detect_profile_from_help("Morphe CLI usage: ...") is MORPHE_CLI


def test_unknown_help_defaults_to_morphe() -> None:
    assert _detect_profile_from_help("nothing helpful here") is MORPHE_CLI


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
        exclude=["patch1"],
        include=["patch2"],
        keystore=Path("ks.keystore"),
        force=True,
        rip_lib=["arm64-v8a"],
    )
    args = MORPHE_CLI.build_patch_args(config)

    assert args[0] == "patch"
    assert args[-1] == "input.apk"
    assert "--input" not in args
    assert args[args.index("-o") + 1] == "output.apk"
    assert "--output" not in args
    assert args[args.index("-p") + 1] == "patches.jar"
    assert "--patch" not in args
    assert args[args.index("-d") + 1] == "patch1"
    assert args[args.index("-e") + 1] == "patch2"
    assert args[args.index("--keystore") + 1] == "ks.keystore"
    assert args[args.index("--striplibs") + 1] == "arm64-v8a"
    assert "-f" in args


def test_morphe_patch_args_inline_options_follow_their_enable_flag() -> None:
    """Inline -O flags follow their enable flag.

    The -O flag sets an option on whichever -e patch precedes it, so option
    flags must be emitted immediately after their patch's -e, in patch order.
    """
    config = PatchCommandConfig(
        apk_path=Path("input.apk"),
        output_path=Path("output.apk"),
        patches_jars=[Path("patches.jar")],
        include=["Patch A", "Patch B"],
        exclusive=True,
        options={
            "Patch A": {"appName": '"Foo"', "disableAds": None},
            "Patch B": {},
        },
    )
    args = MORPHE_CLI.build_patch_args(config)

    a_idx = args.index("Patch A")
    assert args[a_idx - 1] == "-e"
    assert args[a_idx + 1 : a_idx + 6] == ["-O", 'appName="Foo"', "-O", "disableAds", "-e"]

    b_idx = args.index("Patch B")
    assert args[b_idx - 1] == "-e"
    assert args[b_idx + 1] != "-O"
    assert args.index("patches.jar") < a_idx


def test_selections_follow_their_bundle() -> None:
    """Morphe applies -e/-d/-O to the most recent -p, so each selection must sit after its own bundle."""
    config = PatchCommandConfig(
        patches_jars=[Path("a.mpp"), Path("b.mpp")],
        include=["From A", "From B"],
        exclude=["Drop A"],
        options={"From A": {"k": "v"}},
        patch_bundle={"From A": 0, "Drop A": 0, "From B": 1},
    )
    args = MORPHE_CLI.build_patch_args(config)

    assert args[1:] == [
        "-p",
        "a.mpp",
        "-d",
        "Drop A",
        "-e",
        "From A",
        "-O",
        "k=v",
        "-p",
        "b.mpp",
        "-e",
        "From B",
    ]


def test_unknown_patch_goes_to_last_bundle() -> None:
    config = PatchCommandConfig(
        patches_jars=[Path("a.mpp"), Path("b.mpp")],
        include=["Mystery"],
        exclude=["Unlisted"],
    )
    args = MORPHE_CLI.build_patch_args(config)

    b_idx = args.index("b.mpp")
    assert args.index("Mystery") > b_idx
    assert args.index("Unlisted") > b_idx


def test_options_without_include_emit_enable() -> None:
    """Outside exclusive mode, a patch with options but no include entry still gets -e plus its -O flags."""
    config = PatchCommandConfig(
        patches_jars=[Path("a.mpp")],
        options={"Branding": {"appName": '"X"'}, "Excluded": {"k": "v"}},
        exclude=["Excluded"],
    )
    args = MORPHE_CLI.build_patch_args(config)

    idx = args.index("Branding")
    assert args[idx - 1] == "-e"
    assert args[idx + 1 : idx + 3] == ["-O", 'appName="X"']
    assert "k=v" not in args


def test_options_without_include_not_enabled_in_exclusive_mode() -> None:
    config = PatchCommandConfig(
        patches_jars=[Path("a.mpp")],
        include=["Wanted"],
        options={"Other": {"k": "v"}},
        exclusive=True,
    )
    args = MORPHE_CLI.build_patch_args(config)

    assert "Other" not in args
    assert "--exclusive" in args


def test_list_patches_args() -> None:
    """Verify list-patches argument generation."""
    patches = [Path("p1.jar"), Path("p2.jar")]

    morphe_args = MORPHE_CLI.build_list_patches_args(patches)
    assert morphe_args == ["list-patches", "--patches", "p1.jar", "--patches", "p2.jar"]


def test_empty_config() -> None:
    """Verify argument generation with empty config still includes the "patch" subcommand keyword."""
    config = PatchCommandConfig()
    args = MORPHE_CLI.build_patch_args(config)
    assert args == ["patch"]
