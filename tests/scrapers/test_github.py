"""Tests for the GitHub Releases scraper."""

# ruff: noqa: S101

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

from scripts.scrapers.github import GitHubScraper, _find_release, _select_asset, _split_pkg

if TYPE_CHECKING:
    from pathlib import Path

    import pytest

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


BRAVE_URL_PATH = "brave/brave-browser/releases/latest/download/BraveMonoarm64.apk"
BRAVE_ASSETS = [
    {"name": n, "url": f"https://api.github.com/assets/{n}"}
    for n in ("Bravearm64Universal.apk", "BraveMonoarm.apk", "BraveMonoarm64.apk", "BraveMonox64.apk")
]
BRAVE_RELEASES: list[dict[str, Any]] = [
    {"tag_name": "v1.100.9", "name": "Beta v1.100.9", "prerelease": False, "assets": BRAVE_ASSETS},
    {"tag_name": "v1.100.8", "name": "Nightly v1.100.8", "prerelease": True, "assets": BRAVE_ASSETS},
    {"tag_name": "v1.97.57", "name": "Release v1.97.57", "prerelease": False, "assets": BRAVE_ASSETS},
]


class TestSplitPkg:
    """Tests for _split_pkg repo/asset splitting."""

    def test_plain_repo_has_no_asset(self) -> None:
        assert _split_pkg("owner/repo") == ("owner/repo", None)

    def test_trailing_apk_segment_pins_asset(self) -> None:
        assert _split_pkg(BRAVE_URL_PATH) == ("brave/brave-browser", "BraveMonoarm64.apk")

    def test_non_apk_tail_is_ignored(self) -> None:
        assert _split_pkg("owner/repo/releases") == ("owner/repo", None)


class TestBraveStyleReleases:
    """get_versions/download against Brave-style releases (unreliable prerelease flag, arch-less asset names)."""

    @staticmethod
    def _scraper(monkeypatch: pytest.MonkeyPatch) -> GitHubScraper:
        async def fake_list(_self: GitHubScraper, repo: str) -> list[dict[str, Any]]:
            assert repo == "brave/brave-browser"
            return BRAVE_RELEASES

        monkeypatch.setattr(GitHubScraper, "_list_releases", fake_list)
        return GitHubScraper()

    def test_exclude_alpha_beta_keeps_only_release_channel(self, monkeypatch: pytest.MonkeyPatch) -> None:
        scraper = self._scraper(monkeypatch)
        versions = asyncio.run(scraper.get_versions(BRAVE_URL_PATH, exclude_alpha_beta=True))
        assert [v.version for v in versions] == ["v1.97.57"]

    def test_include_beta_returns_everything(self, monkeypatch: pytest.MonkeyPatch) -> None:
        scraper = self._scraper(monkeypatch)
        versions = asyncio.run(scraper.get_versions(BRAVE_URL_PATH, exclude_alpha_beta=False))
        assert len(versions) == len(BRAVE_RELEASES)

    def test_download_picks_pinned_asset(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        scraper = self._scraper(monkeypatch)
        fetched: list[str] = []
        monkeypatch.setattr("scripts.scrapers.github.gh_dl", lambda _dest, url: fetched.append(url) or True)
        result = asyncio.run(scraper.download(BRAVE_URL_PATH, "1.97.57", tmp_path / "out.apk", arch="arm64-v8a"))
        assert result.success
        assert fetched == ["https://api.github.com/assets/BraveMonoarm64.apk"]

    def test_download_missing_pinned_asset_fails(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        scraper = self._scraper(monkeypatch)
        result = asyncio.run(
            scraper.download("brave/brave-browser/Nope.apk", "1.97.57", tmp_path / "out.apk", arch="arm64-v8a")
        )
        assert not result.success
        assert "Nope.apk" in (result.error or "")


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
