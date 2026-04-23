"""Tests for the cache management library."""

# ruff: noqa: S101
from __future__ import annotations

import pytest

from scripts.lib.cache import format_cache_size


@pytest.mark.parametrize(
    ("size_bytes", "expected"),
    [
        (0, "0 bytes"),
        (1, "1 bytes"),
        (1023, "1023 bytes"),
        (1024, "1.0 KiB"),
        (1536, "1.5 KiB"),
        (1048576, "1.0 MiB"),
        (1073741824, "1.0 GiB"),
        (1099511627776, "1.0 TiB"),
        (2199023255552, "2.0 TiB"),
        (1125899906842624, "1024.0 TiB"),
    ],
)
def test_format_cache_size(size_bytes: int, expected: str) -> None:
    """Verify that cache sizes are formatted correctly using IEC units."""
    assert format_cache_size(size_bytes) == expected
