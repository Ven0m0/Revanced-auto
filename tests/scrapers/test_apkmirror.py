"""Tests for APKMirror scraper."""

import pytest

from scripts.scrapers.apkmirror import get_target_archs, ArchType


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
    # ruff: noqa: S101
    assert get_target_archs(arch) == expected
