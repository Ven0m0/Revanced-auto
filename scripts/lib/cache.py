#!/usr/bin/env python3
"""Python cache management with feature parity for the legacy shell cache."""

from __future__ import annotations

import hashlib
import json
import os
import re
import time
from dataclasses import dataclass
from pathlib import Path

DEFAULT_CACHE_TTL = 86400
DEFAULT_CACHE_DIR = "temp"
DEFAULT_CLEAN_PATTERN = ".*"
INDEX_FILE_NAME = ".cache-index.json"


class CacheError(Exception):
    """Raised when cache metadata cannot be loaded or updated safely."""


@dataclass(slots=True)
class CacheEntry:
    """Metadata stored for a cached file."""

    created: int
    accessed: int
    size: int
    checksum: str
    url: str
    ttl: int


@dataclass(slots=True)
class CacheStats:
    """Human-readable cache statistics."""

    total_entries: int
    total_size: int
    expired_entries: int
    cache_directory: Path


@dataclass(slots=True)
class CacheCleanupResult:
    """Counts for cleanup operations."""

    removed_entries: int = 0
    orphaned_entries: int = 0


class CacheManager:
    """Manage cached files using the same on-disk format as the shell cache."""

    def __init__(self, cache_dir: Path | None = None, default_ttl: int = DEFAULT_CACHE_TTL) -> None:
        """Initialize the cache manager.

        Args:
            cache_dir: Cache directory. Defaults to CACHE_DIR or ``temp``.
            default_ttl: Default TTL in seconds.
        """
        cache_root = cache_dir or Path(os.environ.get("CACHE_DIR", DEFAULT_CACHE_DIR))
        self.cache_dir = cache_root
        self.default_ttl = default_ttl
        self.index_file = self.cache_dir / INDEX_FILE_NAME

    def cache_init(self) -> None:
        """Create the cache directory and index file when missing."""
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        if not self.index_file.exists():
            self._write_index({})

    def get_cache_path(self, key: str, subdir: str | None = None) -> Path:
        """Return the cache path for a key.

        Args:
            key: Cache key or filename.
            subdir: Optional subdirectory inside the cache root.

        Returns:
            The full cache path.
        """
        if subdir:
            return self.cache_dir / subdir / key
        return self.cache_dir / key

    def cache_is_valid(self, file_path: Path | str, ttl: int | None = None) -> bool:
        """Check whether a cached file exists, is indexed, unexpired, and intact."""
        cache_path = Path(file_path)
        if not cache_path.is_file() or not self.index_file.exists():
            return False

        entry = self._read_index().get(str(cache_path))
        if entry is None:
            return False

        effective_ttl = entry.ttl if entry.ttl > 0 else ttl or self.default_ttl
        if (int(time.time()) - entry.created) > effective_ttl:
            return False

        if entry.checksum and self._checksum(cache_path) != entry.checksum:
            return False

        return True

    def cache_put(self, file_path: Path | str, source_url: str = "", ttl: int | None = None) -> None:
        """Create or update a cache entry for an existing file.

        Args:
            file_path: Cached file path.
            source_url: Optional source URL.
            ttl: Optional TTL override.

        Raises:
            FileNotFoundError: If the file does not exist.
        """
        cache_path = Path(file_path)
        if not cache_path.is_file():
            msg = f"Cannot cache non-existent file: {cache_path}"
            raise FileNotFoundError(msg)

        self.cache_init()

        timestamp = int(time.time())
        index = self._read_index()
        index[str(cache_path)] = CacheEntry(
            created=timestamp,
            accessed=timestamp,
            size=cache_path.stat().st_size,
            checksum=self._checksum(cache_path),
            url=source_url,
            ttl=ttl or self.default_ttl,
        )
        self._write_index(index)

    def cache_stats(self) -> CacheStats:
        """Return cache statistics."""
        if not self.index_file.exists():
            return CacheStats(
                total_entries=0,
                total_size=0,
                expired_entries=0,
                cache_directory=self.cache_dir,
            )

        index = self._read_index()
        now = int(time.time())
        expired_entries = sum(1 for entry in index.values() if (entry.created + entry.ttl) < now)
        total_size = sum(entry.size for entry in index.values())

        return CacheStats(
            total_entries=len(index),
            total_size=total_size,
            expired_entries=expired_entries,
            cache_directory=self.cache_dir,
        )

    def cache_cleanup(self, force: bool = False) -> CacheCleanupResult:
        """Remove expired entries and optionally orphaned index entries."""
        if not self.index_file.exists():
            return CacheCleanupResult()

        index = self._read_index()
        now = int(time.time())
        expired_keys = [key for key, entry in index.items() if (entry.created + entry.ttl) < now]

        removed_entries = self._remove_entries(index, expired_keys)

        orphaned_entries = 0
        if force:
            orphaned_keys = [key for key in index if not Path(key).is_file()]
            orphaned_entries = self._remove_entries(index, orphaned_keys)

        self._write_index(index)
        return CacheCleanupResult(
            removed_entries=removed_entries,
            orphaned_entries=orphaned_entries,
        )

    def cache_clean_pattern(self, pattern: str = DEFAULT_CLEAN_PATTERN) -> int:
        """Remove cached entries whose keys match a regex pattern."""
        if not self.index_file.exists():
            return 0

        compiled = re.compile(pattern)
        index = self._read_index()
        matched_keys = [key for key in index if compiled.search(key)]
        removed_entries = self._remove_entries(index, matched_keys)
        self._write_index(index)
        return removed_entries

    def _read_index(self) -> dict[str, CacheEntry]:
        """Load the cache index from disk.

        Raises:
            CacheError: If the index is not valid JSON or contains invalid fields.
        """
        try:
            raw_data = json.loads(self.index_file.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return {}
        except json.JSONDecodeError as exc:
            msg = f"Invalid cache index: {self.index_file}"
            raise CacheError(msg) from exc

        if not isinstance(raw_data, dict):
            msg = f"Invalid cache index format: {self.index_file}"
            raise CacheError(msg)

        parsed: dict[str, CacheEntry] = {}
        for key, value in raw_data.items():
            if not isinstance(key, str) or not isinstance(value, dict):
                msg = f"Invalid cache index entry for: {key!r}"
                raise CacheError(msg)
            try:
                parsed[key] = CacheEntry(
                    created=int(value["created"]),
                    accessed=int(value["accessed"]),
                    size=int(value["size"]),
                    checksum=str(value.get("checksum", "")),
                    url=str(value.get("url", "")),
                    ttl=int(value["ttl"]),
                )
            except (KeyError, TypeError, ValueError) as exc:
                msg = f"Invalid cache metadata for: {key}"
                raise CacheError(msg) from exc
        return parsed

    def _write_index(self, index: dict[str, CacheEntry]) -> None:
        """Persist the cache index atomically."""
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        serializable = {
            key: {
                "created": entry.created,
                "accessed": entry.accessed,
                "size": entry.size,
                "checksum": entry.checksum,
                "url": entry.url,
                "ttl": entry.ttl,
            }
            for key, entry in index.items()
        }
        temp_file = self.index_file.with_suffix(".json.tmp")
        temp_file.write_text(
            json.dumps(serializable, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        temp_file.replace(self.index_file)

    def _remove_entries(self, index: dict[str, CacheEntry], keys: list[str]) -> int:
        """Remove indexed entries and any files that still exist."""
        removed_entries = 0
        for key in keys:
            path = Path(key)
            if path.is_file():
                path.unlink()
            if key in index:
                del index[key]
                removed_entries += 1
        return removed_entries

    @staticmethod
    def _checksum(file_path: Path) -> str:
        """Return the SHA-256 checksum for a file."""
        digest = hashlib.sha256()
        with file_path.open("rb") as file_handle:
            for chunk in iter(lambda: file_handle.read(8192), b""):
                digest.update(chunk)
        return digest.hexdigest()


def format_cache_size(size_bytes: int) -> str:
    """Format a size using IEC units."""
    units = ["bytes", "KiB", "MiB", "GiB", "TiB"]
    size = float(size_bytes)
    for unit in units:
        if size < 1024 or unit == units[-1]:
            if unit == "bytes":
                if int(size) == 1:
                    return "1 byte"
                return f"{int(size)} bytes"
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size_bytes} bytes"
