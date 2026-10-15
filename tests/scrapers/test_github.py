"""Tests for the GitHub Releases scraper."""

# ruff: noqa: S101

from __future__ import annotations

from typing import Any

from scripts.scrapers.github import _find_release, _select_asset

RELEASES: list[dict[str, Any]] = [
    {
        "tag_name": "v1.2.0",
        "assets": [
            {"name": "app-1.2.0-arm64-v8a.apk", "url": "https://api.github.com/.../1"},
            {"name": "app-1.2.0-armeabi-v7a.apk", "url": "https://api.github.com/.../2"},
            {"name": "app-1.2.0-all.apkm", "url": "https://api.github.com/.../3"},
        ],
    },
    {
        "tag_name": "v1.1.0",
        "assets": [
            {"name": "app-1.1.0-all.apk", "url": "https://api.github.com/.../4"},
        ],
    },
]


class TestSelectAsset:
    """Tests for _select_asset arch matching."""

    def test_picks_exact_arch_over_all(self) -> None:
        asset = _select_asset(RELEASES[0]["assets"], "arm64-v8a")
        assert asset is not None
        assert asset["name"] == "app-1.2.0-arm64-v8a.apk"

    def test_universal_picks_all_variant(self) -> None:
        asset = _select_asset(RELEASES[1]["assets"], "universal")
        assert asset is not None
        assert asset["name"] == "app-1.1.0-all.apk"

    def test_no_match_returns_none(self) -> None:
        # neither asset is arm64-v8a or "all"; armeabi-v7a-only doesn't fall back.
        assert _select_asset([RELEASES[0]["assets"][1]], "x86_64") is None


class TestFindRelease:
    """Tests for _find_release version matching."""

    def test_finds_by_tag_with_v_prefix_stripped(self) -> None:
        release = _find_release(RELEASES, "1.1.0")
        assert release is not None
        assert release["tag_name"] == "v1.1.0"

    def test_none_version_returns_newest(self) -> None:
        release = _find_release(RELEASES, None)
        assert release is not None
        assert release["tag_name"] == "v1.2.0"

    def test_unknown_version_returns_none(self) -> None:
        assert _find_release(RELEASES, "9.9.9") is None


if __name__ == "__main__":
    # ponytail: assert-based self-check, no pytest needed to sanity-check this module.
    picked = _select_asset(RELEASES[0]["assets"], "arm64-v8a")
    assert picked is not None
    assert picked["name"] == "app-1.2.0-arm64-v8a.apk"
    found = _find_release(RELEASES, "1.1.0")
    assert found is not None
    assert found["tag_name"] == "v1.1.0"
    assert _find_release(RELEASES, "9.9.9") is None
    print("github scraper self-check OK")
