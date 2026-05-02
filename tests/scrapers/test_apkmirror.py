"""Tests for the apkmirror scraper."""

import pytest

from scripts.scrapers.apkmirror import ArchType, get_target_archs


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
    ],
)
def test_get_target_archs(arch: ArchType, expected: list[str]) -> None:
    """Test that get_target_archs returns the correct list of architectures."""
    assert get_target_archs(arch) == expected  # noqa: S101
