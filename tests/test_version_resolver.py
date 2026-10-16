"""Tests for scripts/search/version_resolver.py.

The first samples are hand-written line shapes; TestRealMorpheOutput uses captured real CLI output.
"""

# ruff: noqa: S101

from __future__ import annotations

from scripts.search.version_resolver import parse_patch_names, parse_versions

_LIST_VERSIONS_OUTPUT = """\
INFO: Most common compatible versions:
Package name: com.google.android.youtube
Most common compatible versions:
    20.14.43 (120 patches)
    20.12.46 (118 patches)
    19.47.53 (90 patches)
    20.14.43 (120 patches)
"""

_LIST_PATCHES_OUTPUT = """\
INFO: Index: 0
INFO: Name: Hide ads
Description: Removes ads.
Enabled: true
Compatible packages:
    Package name: com.google.android.youtube
    Compatible versions:
        20.14.43

Index: 1
Name: Custom branding
Description: Changes the app name.
Enabled: false
"""


class TestParseVersions:
    def test_extracts_versions_in_order_without_duplicates(self) -> None:
        assert parse_versions(_LIST_VERSIONS_OUTPUT) == ["20.14.43", "20.12.46", "19.47.53"]

    def test_ignores_non_version_lines(self) -> None:
        assert parse_versions("Package name: com.foo\nAny version\n1\n") == []

    def test_empty_output(self) -> None:
        assert parse_versions("") == []


class TestParsePatchNames:
    def test_extracts_names_with_and_without_info_prefix(self) -> None:
        assert parse_patch_names(_LIST_PATCHES_OUTPUT) == ["Hide ads", "Custom branding"]

    def test_index_and_package_lines_are_not_names(self) -> None:
        names = parse_patch_names(_LIST_PATCHES_OUTPUT)
        assert "0" not in names
        assert "com.google.android.youtube" not in names

    def test_strips_trailing_whitespace(self) -> None:
        assert parse_patch_names("Name: Spoof client   \n") == ["Spoof client"]


# Captured from morphe-cli v1.18.1 with morphe-patches v1.47.0.
_REAL_LIST_VERSIONS_OUTPUT = """\
INFO: Package name: com.google.android.youtube
Most common compatible versions:
\t21.20.405 (96 patches)
\t21.16.256 (96 patches)
\t20.51.39 (96 patches)
\t20.21.37 (96 patches)
"""

_REAL_LIST_PATCHES_OUTPUT = """\
INFO: Index: 0
Name: Clone app
Description: Changes the app package name to allow installing the same app multiple times.
Enabled: false

Index: 1
Name: Change installer source
Description: Spoofs the installer source so the app appears to be installed from an app store.
Enabled: false

Index: 5
Name: Hide ads
Description: Adds options to hide fullscreen ads, Premium promotions and video ads.
Enabled: true
"""


class TestRealMorpheOutput:
    def test_list_versions(self) -> None:
        assert parse_versions(_REAL_LIST_VERSIONS_OUTPUT) == ["21.20.405", "21.16.256", "20.51.39", "20.21.37"]

    def test_list_patches(self) -> None:
        assert parse_patch_names(_REAL_LIST_PATCHES_OUTPUT) == ["Clone app", "Change installer source", "Hide ads"]
