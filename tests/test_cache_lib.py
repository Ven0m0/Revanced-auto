"""Tests for the Python cache library."""

from __future__ import annotations

import json
import re
import time
from pathlib import Path

import pytest

from scripts.lib.cache import CacheError, CacheManager


class TestCacheManager:
    """Tests for CacheManager."""

    def test_cache_init_creates_index(self, tmp_path: Path) -> None:
        """Test cache_init creates the cache directory and index."""
        cache_dir = tmp_path / "cache"
        manager = CacheManager(cache_dir=cache_dir)

        manager.cache_init()

        assert cache_dir.is_dir()
        assert (cache_dir / ".cache-index.json").is_file()
        assert json.loads((cache_dir / ".cache-index.json").read_text(encoding="utf-8")) == {}

    def test_get_cache_path_uses_optional_subdir(self, tmp_path: Path) -> None:
        """Test get_cache_path matches the legacy path layout."""
        manager = CacheManager(cache_dir=tmp_path / "cache")

        assert manager.get_cache_path("file.apk") == tmp_path / "cache" / "file.apk"
        assert manager.get_cache_path("file.apk", "apks") == tmp_path / "cache" / "apks" / "file.apk"

    def test_cache_put_and_cache_is_valid(self, tmp_path: Path) -> None:
        """Test cache_put records metadata and cache_is_valid accepts it."""
        manager = CacheManager(cache_dir=tmp_path / "cache")
        cached_file = tmp_path / "youtube.apk"
        cached_file.write_bytes(b"apk")

        manager.cache_put(cached_file, "https://example.com/file.apk", ttl=60)

        assert manager.cache_is_valid(cached_file)
        index = json.loads((tmp_path / "cache" / ".cache-index.json").read_text(encoding="utf-8"))
        assert index[str(cached_file)]["url"] == "https://example.com/file.apk"
        assert index[str(cached_file)]["ttl"] == 60

    def test_cache_is_valid_rejects_missing_index_entry(self, tmp_path: Path) -> None:
        """Test cache_is_valid returns False when the file is not indexed."""
        manager = CacheManager(cache_dir=tmp_path / "cache")
        manager.cache_init()
        cached_file = tmp_path / "youtube.apk"
        cached_file.write_bytes(b"apk")

        assert not manager.cache_is_valid(cached_file)

    def test_cache_is_valid_rejects_expired_entry(self, tmp_path: Path) -> None:
        """Test cache_is_valid returns False for expired entries."""
        manager = CacheManager(cache_dir=tmp_path / "cache")
        cached_file = tmp_path / "youtube.apk"
        cached_file.write_bytes(b"apk")
        manager.cache_put(cached_file, ttl=1)

        index_file = tmp_path / "cache" / ".cache-index.json"
        index = json.loads(index_file.read_text(encoding="utf-8"))
        index[str(cached_file)]["created"] = int(time.time()) - 10
        index_file.write_text(json.dumps(index), encoding="utf-8")

        assert not manager.cache_is_valid(cached_file)

    def test_cache_is_valid_rejects_checksum_mismatch(self, tmp_path: Path) -> None:
        """Test cache_is_valid returns False when the checksum no longer matches."""
        manager = CacheManager(cache_dir=tmp_path / "cache")
        cached_file = tmp_path / "youtube.apk"
        cached_file.write_bytes(b"apk")
        manager.cache_put(cached_file)
        cached_file.write_bytes(b"modified")

        assert not manager.cache_is_valid(cached_file)

    def test_cache_stats_reports_expired_entries(self, tmp_path: Path) -> None:
        """Test cache_stats includes size and expired counts."""
        manager = CacheManager(cache_dir=tmp_path / "cache")
        first_file = tmp_path / "one.apk"
        second_file = tmp_path / "two.apk"
        first_file.write_bytes(b"1")
        second_file.write_bytes(b"22")
        manager.cache_put(first_file, ttl=1)
        manager.cache_put(second_file, ttl=60)

        index_file = tmp_path / "cache" / ".cache-index.json"
        index = json.loads(index_file.read_text(encoding="utf-8"))
        index[str(first_file)]["created"] = int(time.time()) - 10
        index_file.write_text(json.dumps(index), encoding="utf-8")

        stats = manager.cache_stats()

        assert stats.total_entries == 2
        assert stats.total_size == 3
        assert stats.expired_entries == 1
        assert stats.cache_directory == tmp_path / "cache"

    def test_cache_cleanup_removes_expired_entries(self, tmp_path: Path) -> None:
        """Test cache_cleanup removes expired files and keeps valid ones."""
        manager = CacheManager(cache_dir=tmp_path / "cache")
        expired_file = tmp_path / "expired.apk"
        valid_file = tmp_path / "valid.apk"
        expired_file.write_bytes(b"1")
        valid_file.write_bytes(b"22")
        manager.cache_put(expired_file, ttl=1)
        manager.cache_put(valid_file, ttl=60)

        index_file = tmp_path / "cache" / ".cache-index.json"
        index = json.loads(index_file.read_text(encoding="utf-8"))
        index[str(expired_file)]["created"] = int(time.time()) - 10
        index_file.write_text(json.dumps(index), encoding="utf-8")

        result = manager.cache_cleanup()

        assert result.removed_entries == 1
        assert result.orphaned_entries == 0
        assert not expired_file.exists()
        assert valid_file.exists()

    def test_cache_cleanup_force_removes_orphaned_entries(self, tmp_path: Path) -> None:
        """Test cache_cleanup(force=True) removes orphaned index entries."""
        manager = CacheManager(cache_dir=tmp_path / "cache")
        cached_file = tmp_path / "orphaned.apk"
        cached_file.write_bytes(b"apk")
        manager.cache_put(cached_file, ttl=60)
        cached_file.unlink()

        result = manager.cache_cleanup(force=True)

        assert result.removed_entries == 0
        assert result.orphaned_entries == 1

    def test_cache_clean_pattern_removes_matching_entries(self, tmp_path: Path) -> None:
        """Test cache_clean_pattern removes only matching entries."""
        manager = CacheManager(cache_dir=tmp_path / "cache")
        youtube_file = tmp_path / "youtube.apk"
        spotify_file = tmp_path / "spotify.jar"
        youtube_file.write_bytes(b"1")
        spotify_file.write_bytes(b"22")
        manager.cache_put(youtube_file)
        manager.cache_put(spotify_file)

        removed_entries = manager.cache_clean_pattern(r".*\.apk$")

        assert removed_entries == 1
        assert not youtube_file.exists()
        assert spotify_file.exists()

    def test_cache_clean_pattern_raises_for_invalid_regex(self, tmp_path: Path) -> None:
        """Test cache_clean_pattern raises for invalid regex input."""
        manager = CacheManager(cache_dir=tmp_path / "cache")
        manager.cache_init()

        with pytest.raises(re.error, match="unterminated|missing|bad character"):
            manager.cache_clean_pattern("[")

    def test_cache_put_rejects_missing_file(self, tmp_path: Path) -> None:
        """Test cache_put raises for missing files."""
        manager = CacheManager(cache_dir=tmp_path / "cache")

        with pytest.raises(FileNotFoundError):
            manager.cache_put(tmp_path / "missing.apk")

    def test_invalid_index_raises_cache_error(self, tmp_path: Path) -> None:
        """Test malformed cache index files raise CacheError."""
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()
        (cache_dir / ".cache-index.json").write_text("{not-json", encoding="utf-8")
        manager = CacheManager(cache_dir=cache_dir)

        with pytest.raises(CacheError):
            manager.cache_stats()
