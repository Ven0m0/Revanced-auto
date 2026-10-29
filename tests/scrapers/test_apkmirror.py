"""Tests for APKMirror scraper."""

# ruff: noqa: S101

import re
import zipfile
from types import SimpleNamespace
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, patch

import pytest
from selectolax.lexbor import LexborHTMLParser, LexborNode

from scripts.scrapers.apkmirror import (
    APKMirror,
    ArchType,
    SearchConfig,
    _guess_release_url,
    _is_prerelease,
    _parse_row_data,
    _parse_rows,
    get_target_archs,
    is_apk_bundle,
)
from scripts.scrapers.base import ChallengeError

if TYPE_CHECKING:
    from pathlib import Path

_HEADER_ROW = """
<div class="table-row headerFont">
  <div class="table-cell">Variant</div>
  <div class="table-cell">Architecture</div>
  <div class="table-cell">Minimum Version</div>
  <div class="table-cell">Screen DPI</div>
</div>
"""

_APK_ROW = """
<div class="table-row headerFont">
  <div class="table-cell">
    <a href="/apk/pkg/rel/apk-universal-android-apk-download/">1.2.3</a>
    <span class="apkm-badge">APK</span>
  </div>
  <div class="table-cell">universal</div>
  <div class="table-cell">Android 5.0+</div>
  <div class="table-cell">nodpi</div>
</div>
"""

_BUNDLE_ROW = """
<div class="table-row headerFont">
  <div class="table-cell">
    <a href="/apk/pkg/rel/bundle-arm64-android-apk-download/">1.2.3</a>
    <span class="apkm-badge">BUNDLE</span>
  </div>
  <div class="table-cell">arm64-v8a</div>
  <div class="table-cell">Android 8.0+</div>
  <div class="table-cell">480-640dpi</div>
</div>
"""


_RELEASE_LIST = """
<div class="listWidget">
  <div class="widgetHeader">All versions</div>
  <div class="appRow"><a class="fontBlack" href="/apk/pkg/app/app-2-0-0-release/">App 2.0.0</a></div>
  <div class="appRow"><a class="fontBlack" href="/apk/pkg/app/app-1-0-0-release/">App 1.0.0</a></div>
</div>
"""


class _FakeBrowser:
    instances: list[_FakeBrowser] = []  # noqa: RUF012

    def __init__(self) -> None:
        self.fetch_html = AsyncMock(return_value=_RELEASE_LIST)
        self.aclose = AsyncMock()
        _FakeBrowser.instances.append(self)


def _first_row(html: str) -> LexborNode:
    return _parse_rows(LexborHTMLParser(html))[0]


@pytest.mark.asyncio
async def test_get_versions_falls_back_to_browser_on_challenge_and_closes_it() -> None:
    _FakeBrowser.instances.clear()
    scraper = APKMirror()

    with (
        patch.object(APKMirror, "get", new=AsyncMock(side_effect=ChallengeError("challenge"))),
        patch("scripts.scrapers.apkmirror.ChallengeBrowser", _FakeBrowser),
    ):
        versions = await scraper.get_versions("pkg/app", match_any=True)

    assert [v.version for v in versions] == ["2.0.0", "1.0.0"]
    assert len(_FakeBrowser.instances) == 1
    _FakeBrowser.instances[0].fetch_html.assert_awaited_once_with("https://www.apkmirror.com/apk/pkg/app/")
    _FakeBrowser.instances[0].aclose.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_versions_never_starts_browser_without_challenge() -> None:
    _FakeBrowser.instances.clear()
    scraper = APKMirror()
    response = AsyncMock()
    response.text = _RELEASE_LIST

    with (
        patch.object(APKMirror, "get", new=AsyncMock(return_value=response)),
        patch("scripts.scrapers.apkmirror.ChallengeBrowser", _FakeBrowser),
    ):
        versions = await scraper.get_versions("pkg/app", match_any=True)

    assert len(versions) == 2
    assert _FakeBrowser.instances == []


def test_parse_row_data_rejects_header_row() -> None:
    """The header row has 4 cells too but no <a> in its first cell."""
    assert _parse_row_data(_first_row(_HEADER_ROW)) is None


def test_parse_row_data_reads_apk_row() -> None:
    """A 4-cell variant row (APKMirror dropped the old 5th "download" cell)."""
    row_data = _parse_row_data(_first_row(_APK_ROW))
    assert row_data is not None
    assert row_data.version == "1.2.3"
    assert row_data.bundle == "APK"
    assert row_data.arch == "universal"
    assert row_data.dpi == "nodpi"


def test_search_variant_prefers_apk_over_bundle() -> None:
    """Given both variants for a matching arch, plain APK wins over BUNDLE."""
    html = _APK_ROW + _BUNDLE_ROW
    config = SearchConfig(apk_bundle="APK", arch="universal")
    url = APKMirror()._search_variant(html, config)
    assert url is not None
    assert "apk-universal" in url


def test_search_variant_falls_back_to_bundle_only_release() -> None:
    """A BUNDLE-only release (e.g. Reddit, Brave) must still resolve a URL."""
    config = SearchConfig(apk_bundle="APK", arch="arm64-v8a")
    url = APKMirror()._search_variant(_BUNDLE_ROW, config)
    assert url is not None
    assert "bundle-arm64" in url


@pytest.mark.parametrize(
    ("display_text", "expected"),
    [
        ("YouTube 21.34.248", False),
        ("21.34.248 beta", True),
        ("21.34.248-beta2", True),
        # A channel branded "Beta" as its own product name, not a
        # prerelease marker -- APKMirror lists only that channel's own
        # releases on this page, never mixed with the stable channel.
        ("Brave Beta 1.95.96", False),
    ],
)
def test_is_prerelease(display_text: str, *, expected: bool) -> None:
    """Only a marker after the version number counts as a prerelease flag."""
    version_match = re.search(r"\d+(?:\.\d+)+", display_text)
    assert version_match is not None
    assert _is_prerelease(display_text, version_match) is expected


_APKM = "https://www.apkmirror.com/apk"


@pytest.mark.parametrize(
    ("releases", "version", "expected"),
    [
        # The three real releases that sit beyond the app page's short listing.
        (
            [("TikTok 47.5.3", f"{_APKM}/tiktok-pte-ltd/tik-tok-including-musical-ly/tiktok-47-5-3-release/")],
            "47.4.3",
            f"{_APKM}/tiktok-pte-ltd/tik-tok-including-musical-ly/tiktok-47-4-3-release/",
        ),
        (
            [("Google Maps 26.42.02.997557324", f"{_APKM}/google-inc/maps/google-maps-26-42-02-997557324-release/")],
            "26.36.04.973607363",
            f"{_APKM}/google-inc/maps/google-maps-26-36-04-973607363-release/",
        ),
        # SoundCloud's slug prefix changed over time: the oldest listed row must be the template.
        (
            [
                (
                    "SoundCloud: Discover Music 2026.10.21-release",
                    f"{_APKM}/soundcloud/soundcloud-soundcloud/soundcloud-discover-music-2026-10-21-release-release/",
                ),
                (
                    "SoundCloud: Discover Music 2026.09.23-release",
                    f"{_APKM}/soundcloud/soundcloud-soundcloud/soundcloud-the-music-you-love-2026-09-23-release-release/",
                ),
            ],
            "2026.09.09",
            f"{_APKM}/soundcloud/soundcloud-soundcloud/soundcloud-the-music-you-love-2026-09-09-release-release/",
        ),
        # A prerelease row has a different slug suffix, so it must not be the template.
        (
            [
                ("App 2.0.0", f"{_APKM}/p/app/app-2-0-0-release/"),
                ("App 1.5.0 beta", f"{_APKM}/p/app/app-1-5-0-beta-release/"),
            ],
            "1.0.0",
            f"{_APKM}/p/app/app-1-0-0-release/",
        ),
        ([], "1.0.0", None),
    ],
)
def test_guess_release_url(releases: list[tuple[str, str]], version: str, expected: str | None) -> None:
    assert _guess_release_url(releases, version) == expected


_SHORT_LISTING = """
<div class="listWidget">
  <div class="widgetHeader">All versions</div>
  <div class="appRow"><a class="fontBlack" href="/apk/pkg/app/app-5-0-0-release/">App 5.0.0</a></div>
  <div class="appRow"><a class="fontBlack" href="/apk/pkg/app/app-4-0-0-release/">App 4.0.0</a></div>
</div>
"""
_LISTING_URL = f"{_APKM}/pkg/app/"
_OLD_RELEASE_URL = f"{_APKM}/pkg/app/app-3-0-0-release/"


def _fake_get(pages: dict[str, str]) -> AsyncMock:
    async def get(url: str, use_cache: bool = True) -> SimpleNamespace:  # noqa: ARG001, FBT001, FBT002
        if url not in pages:
            msg = f"HTTP 404 for {url}"
            raise RuntimeError(msg)
        return SimpleNamespace(text=pages[url])

    return AsyncMock(side_effect=get)


@pytest.mark.asyncio
async def test_get_versions_probes_compatible_version_beyond_the_listing() -> None:
    fake_get = _fake_get({_LISTING_URL: _SHORT_LISTING, _OLD_RELEASE_URL: _APK_ROW})

    with patch.object(APKMirror, "get", new=fake_get):
        versions = await APKMirror().get_versions("pkg/app", match_any=True, compatible=["3.0.0", "2.0.0"])

    assert [(v.version, v.url) for v in versions] == [
        ("5.0.0", f"{_APKM}/pkg/app/app-5-0-0-release/"),
        ("4.0.0", f"{_APKM}/pkg/app/app-4-0-0-release/"),
        ("3.0.0", _OLD_RELEASE_URL),
    ]
    # The newest compatible hit ends the probing; 2.0.0 is never requested.
    assert f"{_APKM}/pkg/app/app-2-0-0-release/" not in [c.args[0] for c in fake_get.await_args_list]


@pytest.mark.asyncio
async def test_get_versions_skips_probe_when_a_compatible_version_is_listed() -> None:
    fake_get = _fake_get({_LISTING_URL: _SHORT_LISTING})

    with patch.object(APKMirror, "get", new=fake_get):
        versions = await APKMirror().get_versions("pkg/app", match_any=True, compatible=["4.0.0", "3.0.0"])

    assert [v.version for v in versions] == ["5.0.0", "4.0.0"]
    fake_get.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_versions_probe_finds_nothing_when_release_page_is_missing() -> None:
    fake_get = _fake_get({_LISTING_URL: _SHORT_LISTING})

    with patch.object(APKMirror, "get", new=fake_get):
        versions = await APKMirror().get_versions("pkg/app", match_any=True, compatible=["3.0.0"])

    assert [v.version for v in versions] == ["5.0.0", "4.0.0"]


@pytest.mark.asyncio
async def test_download_fetches_release_beyond_the_listing(tmp_path: Path) -> None:
    fake_get = _fake_get({_LISTING_URL: _SHORT_LISTING, _OLD_RELEASE_URL: _APK_ROW})
    get_download_url = AsyncMock(return_value="https://www.apkmirror.com/final.apk")

    with (
        patch.object(APKMirror, "get", new=fake_get),
        patch.object(APKMirror, "_get_download_url", new=get_download_url),
        patch.object(APKMirror, "save", new=AsyncMock()),
    ):
        result = await APKMirror().download("pkg/app", "3.0.0", tmp_path / "app.apk")

    assert result.success
    assert result.version == "3.0.0"
    get_download_url.assert_awaited_once()
    call = get_download_url.await_args
    assert call is not None
    assert "apk-universal" in call.args[0]


@pytest.mark.parametrize(
    ("arch", "expected"),
    [
        (
            "all",
            ["universal", "noarch", "arm64-v8a + armeabi-v7a"],
        ),
        (
            "arm64-v8a",
            ["arm64-v8a", "universal", "noarch", "arm64-v8a + armeabi-v7a"],
        ),
        (
            "armeabi-v7a",
            ["armeabi-v7a", "universal", "noarch", "arm64-v8a + armeabi-v7a"],
        ),
        (
            "x86",
            ["x86", "universal", "noarch", "arm64-v8a + armeabi-v7a"],
        ),
        (
            "x86_64",
            ["x86_64", "universal", "noarch", "arm64-v8a + armeabi-v7a"],
        ),
        (
            "universal",
            ["universal", "universal", "noarch", "arm64-v8a + armeabi-v7a"],
        ),
        (
            "noarch",
            ["noarch", "universal", "noarch", "arm64-v8a + armeabi-v7a"],
        ),
    ],
)
def test_get_target_archs(arch: ArchType, expected: list[str]) -> None:
    """Test getting compatible architectures.

    Verifies that the function correctly maps a requested architecture
    to a list of acceptable architectures, including fallbacks.
    """
    assert get_target_archs(arch) == expected


def test_is_apk_bundle_detects_split_bundle(sample_xapk: Path) -> None:
    """A bundle zip (splits, no root AndroidManifest.xml) is detected."""
    assert is_apk_bundle(sample_xapk) is True


def test_is_apk_bundle_rejects_apk_named_bundle_bytes(sample_xapk: Path, tmp_path: Path) -> None:
    """The real regression: APKMirror always saves to a ``.apk``-suffixed path.

    Even when the downloaded bytes are actually a split bundle. Detection must
    look at content, not the filename the caller happened to choose.
    """
    apk_named_bundle = tmp_path / "downloaded.apk"
    apk_named_bundle.write_bytes(sample_xapk.read_bytes())
    assert is_apk_bundle(apk_named_bundle) is True


def test_is_apk_bundle_rejects_real_apk(tmp_path: Path) -> None:
    """A zip containing a root AndroidManifest.xml is a real installable APK."""
    real_apk = tmp_path / "real.apk"
    with zipfile.ZipFile(real_apk, "w") as zf:
        zf.writestr("AndroidManifest.xml", b"\x00")
        zf.writestr("classes.dex", b"\x00")
    assert is_apk_bundle(real_apk) is False


def test_is_apk_bundle_rejects_non_zip(tmp_path: Path) -> None:
    """A non-zip file (e.g. a truncated/failed download) is not a bundle."""
    not_a_zip = tmp_path / "broken.apk"
    not_a_zip.write_bytes(b"not a zip file")
    assert is_apk_bundle(not_a_zip) is False
