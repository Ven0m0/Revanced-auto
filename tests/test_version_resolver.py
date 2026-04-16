"""Tests for scripts/search/version_resolver.py."""

# ruff: noqa: D101, D102, S101

from __future__ import annotations

import pytest

from scripts.search.version_resolver import VersionResolver


@pytest.fixture
def resolver() -> VersionResolver:
    return VersionResolver()


class TestVersionParsing:
    def test_parse_list_patches_simple(self, resolver: VersionResolver) -> None:
        output = """
com.google.android.youtube
  18.01.38
  18.05.40
com.google.android.apps.photos
  6.20.0.504285223
"""
        parsed = resolver._parse_list_patches(output)
        assert "com.google.android.youtube" in parsed
        assert "18.01.38" in parsed["com.google.android.youtube"]
        assert "18.05.40" in parsed["com.google.android.youtube"]
        assert "com.google.android.apps.photos" in parsed
        assert "6.20.0.504285223" in parsed["com.google.android.apps.photos"]

    def test_parse_list_patches_with_colons(self, resolver: VersionResolver) -> None:
        # Some CLI versions might output package: version or similar
        output = """
com.google.android.youtube:
  18.01.38
"""
        parsed = resolver._parse_list_patches(output)
        assert "com.google.android.youtube" in parsed
        assert "18.01.38" in parsed["com.google.android.youtube"]

    def test_extract_package_name(self, resolver: VersionResolver) -> None:
        assert resolver._extract_package_name("com.example.app") == "com.example.app"
        assert resolver._extract_package_name("com.example.app:") == "com.example.app"
        # _is_package_line uses re.match (starts at beginning)
        assert resolver._extract_package_name("  com.example.app") is None

    def test_is_version_line(self, resolver: VersionResolver) -> None:
        assert resolver._is_version_line("  18.01.38") is True
        assert resolver._is_version_line("  18.01.38-beta") is True
        assert resolver._is_version_line("  not a version") is False


class TestVersionClassification:
    def test_is_beta_version(self, resolver: VersionResolver) -> None:
        assert resolver._is_beta_version("18.01.38") is False
        assert resolver._is_beta_version("18.01.38-beta") is True
        assert resolver._is_beta_version("18.01.38.b1") is True
        assert resolver._is_beta_version("18.01.38-rc01") is True
        assert resolver._is_beta_version("18.01.38-alpha") is True
        assert resolver._is_beta_version("18.01.38-pre") is True
        assert resolver._is_beta_version("18.01.38.pre1") is True


class TestVersionNormalizationAndSorting:
    def test_normalize_version(self, resolver: VersionResolver) -> None:
        assert resolver._normalize_version("18.01.38") == "18.01.38"
        assert resolver._normalize_version("v18.01.38") == "18.01.38"
        assert resolver._normalize_version("18.01.38-beta") == "18.01.38-"  # '-' is preserved

    def test_version_sort_key(self, resolver: VersionResolver) -> None:
        versions = ["1.2.10", "1.10.2", "1.2.9"]
        sorted_versions = sorted(versions, key=resolver._version_sort_key)
        assert sorted_versions == ["1.2.9", "1.2.10", "1.10.2"]

    def test_version_sort_key_with_non_numeric(self, resolver: VersionResolver) -> None:
        # 1.2.3-beta vs 1.2.3
        v1 = "1.2.3-beta"
        v2 = "1.2.3"
        assert resolver._version_sort_key(v1) == ((1, 2, 3), "1.2.3-beta")
        assert resolver._version_sort_key(v2) == ((1, 2, 3), "1.2.3")
        # "1.2.3-beta" > "1.2.3" in string comparison because '-' > nothing (implicit)
        assert resolver._version_sort_key(v1) > resolver._version_sort_key(v2)


class TestVersionResolution:
    def test_get_version_auto(self, resolver: VersionResolver) -> None:
        output = "pkg.a\n 1.0.0\n 1.1.0\n 1.2.0-beta"
        # auto mode returns highest compatible.
        assert resolver.get_version("pkg.a", "auto", output) == "1.2.0-beta"

    def test_get_version_latest(self, resolver: VersionResolver) -> None:
        output = "pkg.a\n 1.0.0\n 1.1.0\n 1.2.0-beta"
        # latest mode filters out betas, then gets highest compatible.
        assert resolver.get_version("pkg.a", "latest", output) == "1.1.0"

    def test_get_version_beta(self, resolver: VersionResolver) -> None:
        output = "pkg.a\n 1.0.0\n 1.1.0\n 1.2.0-beta"
        # beta mode includes betas.
        assert resolver.get_version("pkg.a", "beta", output) == "1.2.0-beta"

    def test_get_version_specific(self, resolver: VersionResolver) -> None:
        output = "pkg.a\n 1.0.0\n 1.1.0"
        assert resolver.get_version("pkg.a", "1.0.0", output) == "1.0.0"
        assert resolver.get_version("pkg.a", "v1.1.0", output) == "1.1.0"  # normalized match
        assert resolver.get_version("pkg.a", "2.0.0", output) is None


class TestCompatibilityLogic:
    def test_is_version_compatible_stub(self, resolver: VersionResolver) -> None:
        # Current implementation: returns False if include or exclude is not empty
        assert resolver._is_version_compatible("1.0.0", set(), set()) is True
        assert resolver._is_version_compatible("1.0.0", {"patch1"}, set()) is False
        assert resolver._is_version_compatible("1.0.0", set(), {"patch2"}) is False

    def test_get_version_with_patches_fails(self, resolver: VersionResolver) -> None:
        output = "pkg.a\n 1.0.0\n 1.1.0"
        # Since _is_version_compatible returns False for any patches,
        # it should fall back to the last version in sorted list.
        # sorted_versions (desc) = [1.1.0, 1.0.0]
        # if all incompatible, returns sorted_versions[-1] which is 1.0.0
        assert resolver.get_version("pkg.a", "auto", output, include_patches=["p1"]) == "1.0.0"
