"""Tests for APKMirror scraper."""

# ruff: noqa: S101

import re
import zipfile
from typing import TYPE_CHECKING

import pytest
from selectolax.parser import HTMLParser, Node

from scripts.scrapers.apkmirror import (
    APKMirror,
    ArchType,
    SearchConfig,
    _is_prerelease,
    _parse_row_data,
    _parse_rows,
    get_target_archs,
    is_apk_bundle,
)

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


def _first_row(html: str) -> Node:
    return _parse_rows(HTMLParser(html))[0]


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
