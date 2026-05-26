"""Tests for scripts/builder/cli_profiles.py."""

# ruff: noqa: S101

from __future__ import annotations

from scripts.builder.cli_profiles import (
    ADOBO_CLI,
    BUILTIN_PROFILES,
    MORPHE_CLI,
    REVANCED_CLI_V5,
    REVANCED_CLI_V6,
    CLIProfileType,
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
