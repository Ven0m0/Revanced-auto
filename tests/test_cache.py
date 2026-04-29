"""Tests for scripts/lib/cache.py."""

# ruff: noqa: S101
from __future__ import annotations

import json
import time
from typing import TYPE_CHECKING

import pytest

from scripts.lib.cache import (
    CacheError,
    CacheManager,
    format_cache_size,
)

if TYPE_CHECKING:
    from pathlib import Path


@pytest.mark.parametrize(
    ("size_bytes", "expected"),
    [
        (0, "0 bytes"),
        (1, "1 byte"),
        (1023, "1023 bytes"),
        (1024, "1.0 KiB"),
        (1536, "1.5 KiB"),
        (1024**2, "1.0 MiB"),
        (1024**3, "1.0 GiB"),
        (1024**4, "1.0 TiB"),
        (2 * 1024**4, "2.0 TiB"),
        (1024**5, "1024.0 TiB"),
        (int(1024 * 1.1), "1.1 KiB"),
        (int(1024**2 * 1.1), "1.1 MiB"),
        (1024**2 - 1, "1024.0 KiB"),
    ],
)
def test_format_cache_size(size_bytes: int, expected: str) -> None:
    """Verify that cache sizes are formatted correctly using IEC units."""
    assert format_cache_size(size_bytes) == expected


class TestCacheManager:
    """Unit tests for the CacheManager class."""

    @pytest.fixture
    def cache_manager(self, tmp_path: Path) -> CacheManager:
        """Provide a CacheManager instance using a temporary directory."""
        return CacheManager(cache_dir=tmp_path)

    def test_cache_init(self, cache_manager: CacheManager, tmp_path: Path) -> None:
        """Verify that cache_init creates the directory and index file."""
        index_file = tmp_path / ".cache-index.json"
        assert not index_file.exists()

        cache_manager.cache_init()
        assert tmp_path.exists()
        assert index_file.exists()
        assert json.loads(index_file.read_text()) == {}

    def test_get_cache_path(self, cache_manager: CacheManager, tmp_path: Path) -> None:
        """Verify that get_cache_path returns the correct path."""
        assert cache_manager.get_cache_path("test.txt") == tmp_path / "test.txt"
        assert cache_manager.get_cache_path("test.txt", subdir="sub") == tmp_path / "sub" / "test.txt"

    def test_cache_put_and_is_valid(self, cache_manager: CacheManager, tmp_path: Path) -> None:
        """Verify basic cache put and validity check."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("hello world")

        cache_manager.cache_put(test_file)

        assert cache_manager.cache_is_valid(test_file)
        assert (tmp_path / ".cache-index.json").exists()

    def test_cache_is_valid_expired(
        self, cache_manager: CacheManager, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verify that expired cache entries are considered invalid."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("hello")

        now = int(time.time())
        monkeypatch.setattr(time, "time", lambda: now)
        cache_manager.cache_put(test_file, ttl=10)

        assert cache_manager.cache_is_valid(test_file)

        # Fast forward time
        monkeypatch.setattr(time, "time", lambda: now + 20)
        assert not cache_manager.cache_is_valid(test_file)

    def test_cache_is_valid_checksum_mismatch(self, cache_manager: CacheManager, tmp_path: Path) -> None:
        """Verify that cache entries with checksum mismatch are considered invalid."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("hello")

        cache_manager.cache_put(test_file)
        assert cache_manager.cache_is_valid(test_file)

        # Modify file content
        test_file.write_text("world")
        assert not cache_manager.cache_is_valid(test_file)

    def test_cache_stats(self, cache_manager: CacheManager, tmp_path: Path) -> None:
        """Verify that cache_stats returns accurate statistics."""
        f1 = tmp_path / "f1.txt"
        f1.write_text("a")  # 1 byte
        f2 = tmp_path / "f2.txt"
        f2.write_text("bb")  # 2 bytes

        cache_manager.cache_put(f1)
        cache_manager.cache_put(f2)

        stats = cache_manager.cache_stats()
        assert stats.total_entries == 2
        assert stats.total_size == 3
        assert stats.cache_directory == tmp_path

    def test_cache_cleanup(self, cache_manager: CacheManager, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verify that cache_cleanup removes expired entries."""
        f1 = tmp_path / "f1.txt"
        f1.write_text("content")

        now = int(time.time())
        monkeypatch.setattr(time, "time", lambda: now)
        cache_manager.cache_put(f1, ttl=10)

        # Not expired yet
        res = cache_manager.cache_cleanup()
        assert res.removed_entries == 0
        assert f1.exists()

        # Expire it
        monkeypatch.setattr(time, "time", lambda: now + 20)
        res = cache_manager.cache_cleanup()
        assert res.removed_entries == 1
        assert not f1.exists()

    def test_cache_cleanup_orphaned(self, cache_manager: CacheManager, tmp_path: Path) -> None:
        """Verify that cache_cleanup removes orphaned entries when forced."""
        f1 = tmp_path / "f1.txt"
        f1.write_text("content")
        cache_manager.cache_put(f1)

        f1.unlink()  # Remove file but leave in index

        # Normal cleanup shouldn't remove it if not expired
        res = cache_manager.cache_cleanup(force=False)
        assert res.orphaned_entries == 0

        # Forced cleanup should remove it
        res = cache_manager.cache_cleanup(force=True)
        assert res.orphaned_entries == 1

    def test_cache_clean_pattern(self, cache_manager: CacheManager, tmp_path: Path) -> None:
        """Verify that cache_clean_pattern removes matching entries."""
        f1 = tmp_path / "match_this.txt"
        f1.write_text("content")
        f2 = tmp_path / "keep_this.txt"
        f2.write_text("content")

        cache_manager.cache_put(f1)
        cache_manager.cache_put(f2)

        removed = cache_manager.cache_clean_pattern("match")
        assert removed == 1
        assert not f1.exists()
        assert f2.exists()

    def test_read_index_corrupted(self, cache_manager: CacheManager, tmp_path: Path) -> None:
        """Verify handling of corrupted index file."""
        cache_manager.cache_init()
        index_file = tmp_path / ".cache-index.json"
        index_file.write_text("not json")

        with pytest.raises(CacheError, match="Invalid cache index"):
            cache_manager.cache_stats()

    def test_cache_put_non_existent(self, cache_manager: CacheManager, tmp_path: Path) -> None:
        """Verify that cache_put raises FileNotFoundError for missing files."""
        with pytest.raises(FileNotFoundError):
            cache_manager.cache_put(tmp_path / "non_existent.txt")
