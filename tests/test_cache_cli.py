"""CLI tests for Python cache subcommands."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent


def run_cli(*args: str, cache_dir: Path) -> subprocess.CompletedProcess[str]:
    """Run the CLI with an isolated cache directory."""
    env = os.environ.copy()
    env["CACHE_DIR"] = str(cache_dir)
    env["PYTHONPATH"] = str(REPO_ROOT)
    return subprocess.run(
        [sys.executable, "-m", "scripts.cli", *args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )


class TestCacheCLI:
    """Tests for cache subcommands in the Python CLI."""

    def test_cache_init_creates_index(self, tmp_path: Path) -> None:
        """Test `cache init` creates the index file."""
        result = run_cli("cache", "init", cache_dir=tmp_path / "cache")

        assert result.returncode == 0
        assert "Cache initialized" in result.stdout
        assert (tmp_path / "cache" / ".cache-index.json").is_file()

    def test_cache_stats_reports_values(self, tmp_path: Path) -> None:
        """Test `cache stats` prints the expected summary."""
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()
        file_path = tmp_path / "youtube.apk"
        file_path.write_bytes(b"apk")
        index = {
            str(file_path): {
                "created": 1,
                "accessed": 1,
                "size": 3,
                "checksum": "",
                "url": "",
                "ttl": 9999999999,
            }
        }
        (cache_dir / ".cache-index.json").write_text(json.dumps(index), encoding="utf-8")

        result = run_cli("cache", "stats", cache_dir=cache_dir)

        assert result.returncode == 0
        assert "Cache Statistics:" in result.stdout
        assert "Total entries: 1" in result.stdout
        assert "Expired entries: 0" in result.stdout

    def test_cache_cleanup_supports_legacy_force_argument(self, tmp_path: Path) -> None:
        """Test `cache cleanup force` accepts the legacy positional form."""
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()
        orphaned_file = tmp_path / "missing.apk"
        index = {
            str(orphaned_file): {
                "created": 1,
                "accessed": 1,
                "size": 3,
                "checksum": "",
                "url": "",
                "ttl": 9999999999,
            }
        }
        (cache_dir / ".cache-index.json").write_text(json.dumps(index), encoding="utf-8")

        result = run_cli("cache", "cleanup", "force", cache_dir=cache_dir)

        assert result.returncode == 0
        assert "Removed 1 orphaned index entries" in result.stdout

    def test_cache_clean_supports_legacy_pattern_argument(self, tmp_path: Path) -> None:
        """Test `cache clean` accepts the legacy positional pattern form."""
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()
        apk_file = tmp_path / "youtube.apk"
        jar_file = tmp_path / "cli.jar"
        apk_file.write_bytes(b"1")
        jar_file.write_bytes(b"2")
        index = {
            str(apk_file): {
                "created": 1,
                "accessed": 1,
                "size": 1,
                "checksum": "",
                "url": "",
                "ttl": 9999999999,
            },
            str(jar_file): {
                "created": 1,
                "accessed": 1,
                "size": 1,
                "checksum": "",
                "url": "",
                "ttl": 9999999999,
            },
        }
        (cache_dir / ".cache-index.json").write_text(json.dumps(index), encoding="utf-8")

        result = run_cli("cache", "clean", r".*\.apk$", cache_dir=cache_dir)

        assert result.returncode == 0
        assert "Removed 1 cache entries" in result.stdout
        assert not apk_file.exists()
        assert jar_file.exists()

    def test_cache_command_reports_invalid_regex(self, tmp_path: Path) -> None:
        """Test invalid regex patterns fail with a non-zero exit status."""
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()
        (cache_dir / ".cache-index.json").write_text("{}", encoding="utf-8")

        result = run_cli("cache", "clean", "[", cache_dir=cache_dir)

        assert result.returncode == 1
        assert "Cache command failed:" in result.stderr
