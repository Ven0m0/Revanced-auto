#!/usr/bin/env python3
"""Tests for CLI argument compatibility profiles."""

from __future__ import annotations

from pathlib import Path

import pytest

from scripts.builder.cli_profiles import (
    MORPHE_CLI,
    REVANCED_CLI_V5,
    REVANCED_CLI_V6,
    PatchCommandConfig,
)

# ruff: noqa: S101


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
    """Verify Morphe CLI argument generation."""
    config = PatchCommandConfig(
        apk_path=Path("input.apk"),
        output_path=Path("output.apk"),
        patches_jars=[Path("patches.jar")],
    )
    args = MORPHE_CLI.build_patch_args(config)

    assert "--input" in args
    assert "input.apk" in args
    assert "--output" in args
    assert "output.apk" in args
    assert "--patch" in args
    assert "patches.jar" in args


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
    """Verify argument generation with empty config."""
    config = PatchCommandConfig()
    args = REVANCED_CLI_V6.build_patch_args(config)
    assert args == []
