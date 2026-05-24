"""Tests for scripts/lib/cache.py."""

# ruff: noqa: S101
from __future__ import annotations

import hashlib
import json
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pathlib import Path

from scripts.lib.cache import CacheEntry, CacheManager, format_cache_size


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
    ],
)
def test_format_cache_size(size_bytes: int, expected: str) -> None:
    """Verify that cache sizes are formatted correctly using IEC units."""
    assert format_cache_size(size_bytes) == expected


class TestCacheManager:
    """Tests for the CacheManager class."""

    @pytest.fixture
    def cache_dir(self, tmp_path: Path) -> Path:
        """Create a temporary cache directory."""
        return tmp_path / "cache"

    @pytest.fixture
    def manager(self, cache_dir: Path) -> CacheManager:
        """Create a CacheManager instance."""
        return CacheManager(cache_dir=cache_dir)

    def test_cache_init(self, manager: CacheManager, cache_dir: Path) -> None:
        """Verify that cache_init creates the directory and index file."""
        manager.cache_init()
        assert cache_dir.is_dir()
        assert (cache_dir / ".cache-index.json").is_file()
        assert json.loads((cache_dir / ".cache-index.json").read_text()) == {}

    def test_cache_put_and_is_valid(self, manager: CacheManager, cache_dir: Path) -> None:
        """Verify that files can be cached and validated."""
        test_file = cache_dir / "test.txt"
        cache_dir.mkdir(parents=True, exist_ok=True)
        test_file.write_text("hello world")

        manager.cache_put(test_file)

        assert manager.cache_is_valid(test_file)

        # Verify index entry
        with (cache_dir / ".cache-index.json").open() as f:
            index = json.load(f)
            assert str(test_file) in index
            entry = index[str(test_file)]
            assert entry["size"] == len("hello world")
            assert entry["checksum"] == hashlib.sha256(b"hello world").hexdigest()

    def test_cache_is_valid_expired(self, manager: CacheManager, cache_dir: Path) -> None:
        """Verify that expired cache entries are invalid."""
        test_file = cache_dir / "test.txt"
        cache_dir.mkdir(parents=True, exist_ok=True)
        test_file.write_text("hello world")

        # Put with a very old creation time by manually updating the index
        manager.cache_put(test_file)
        index = manager._read_index()
        entry = index[str(test_file)]
        index[str(test_file)] = CacheEntry(
            created=entry.created - 100000,
            accessed=entry.accessed,
            size=entry.size,
            checksum=entry.checksum,
            url=entry.url,
            ttl=3600,
        )
        manager._write_index(index)

        assert not manager.cache_is_valid(test_file)

    def test_cache_is_valid_checksum_mismatch(self, manager: CacheManager, cache_dir: Path) -> None:
        """Verify that files with mismatched checksums are invalid."""
        test_file = cache_dir / "test.txt"
        cache_dir.mkdir(parents=True, exist_ok=True)
        test_file.write_text("hello world")

        manager.cache_put(test_file)
        assert manager.cache_is_valid(test_file)

        # Modify file content
        test_file.write_text("corrupted")
        assert not manager.cache_is_valid(test_file)

    def test_cache_stats(self, manager: CacheManager, cache_dir: Path) -> None:
        """Verify cache statistics calculation."""
        test_file1 = cache_dir / "test1.txt"
        test_file2 = cache_dir / "test2.txt"
        cache_dir.mkdir(parents=True, exist_ok=True)
        test_file1.write_text("one")
        test_file2.write_text("three")

        manager.cache_put(test_file1)

        # Manually add an expired entry
        manager.cache_put(test_file2)
        index = manager._read_index()
        entry = index[str(test_file2)]
        index[str(test_file2)] = CacheEntry(
            created=entry.created - 100000,
            accessed=entry.accessed,
            size=entry.size,
            checksum=entry.checksum,
            url=entry.url,
            ttl=3600,
        )
        manager._write_index(index)

        stats = manager.cache_stats()
        assert stats.total_entries == 2
        assert stats.total_size == 3 + 5
        assert stats.expired_entries == 1
        assert stats.cache_directory == cache_dir

    def test_cache_cleanup(self, manager: CacheManager, cache_dir: Path) -> None:
        """Verify that expired and orphaned entries are cleaned up."""
        test_file1 = cache_dir / "test1.txt"
        test_file2 = cache_dir / "test2.txt"
        cache_dir.mkdir(parents=True, exist_ok=True)
        test_file1.write_text("valid")
        test_file2.write_text("expired")

        manager.cache_put(test_file1)

        # Manually add an expired entry
        manager.cache_put(test_file2)
        index = manager._read_index()
        entry = index[str(test_file2)]
        index[str(test_file2)] = CacheEntry(
            created=entry.created - 100000,
            accessed=entry.accessed,
            size=entry.size,
            checksum=entry.checksum,
            url=entry.url,
            ttl=3600,
        )
        manager._write_index(index)

        # Add orphaned entry manually to index
        index = manager._read_index()
        orphaned_path = cache_dir / "orphaned.txt"
        index[str(orphaned_path)] = index[str(test_file1)]
        manager._write_index(index)

        # Cleanup expired
        result = manager.cache_cleanup()
        assert result.removed_entries == 1
        assert not test_file2.exists()
        assert test_file1.exists()

        # Cleanup orphaned
        result = manager.cache_cleanup(force=True)
        assert result.orphaned_entries == 1
        assert str(orphaned_path) not in manager._read_index()

    def test_cache_clean_pattern(self, manager: CacheManager, cache_dir: Path) -> None:
        """Verify pattern-based cache clearing."""
        test_file1 = cache_dir / "app1.apk"
        test_file2 = cache_dir / "app2.apk"
        cache_dir.mkdir(parents=True, exist_ok=True)
        test_file1.write_text("apk1")
        test_file2.write_text("apk2")

        manager.cache_put(test_file1)
        manager.cache_put(test_file2)

        removed = manager.cache_clean_pattern("app1")
        assert removed == 1
        assert not test_file1.exists()
        assert test_file2.exists()

    def test_get_cache_path(self, manager: CacheManager, cache_dir: Path) -> None:
        """Verify cache path generation."""
        assert manager.get_cache_path("test.txt") == cache_dir / "test.txt"
        assert manager.get_cache_path("test.txt", subdir="apps") == cache_dir / "apps" / "test.txt"
