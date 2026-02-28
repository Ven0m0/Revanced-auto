"""Test suite for Uptodown search logic."""

import sys
import unittest
from pathlib import Path

# Add the project root to sys.path to ensure we can import scripts
sys.path.append(str(Path(__file__).resolve().parent.parent))

from scripts.uptodown_search import search


class TestUptodownSearch(unittest.TestCase):
    """Test suite for Uptodown search logic."""

    def test_match_found(self) -> None:
        """Test basic match with no whitespace between elements."""
        content = '<p>arm64-v8a</p><div class="v-report" data-file-id="12345"></div>'
        assert search(content, ["arm64-v8a"]) == "12345"  # noqa: S101

    def test_no_match_arch(self) -> None:
        """Test when architecture doesn't match allowed list."""
        content = '<p>armeabi-v7a</p><div class="v-report" data-file-id="12345"></div>'
        assert search(content, ["arm64-v8a"]) is None  # noqa: S101

    def test_no_match_structure(self) -> None:
        """Test when missing the following div."""
        content = "<p>arm64-v8a</p>"
        assert search(content, ["arm64-v8a"]) is None  # noqa: S101

    def test_missing_file_id(self) -> None:
        """Test when div exists but no data-file-id attribute."""
        content = '<p>arm64-v8a</p><div class="v-report"></div>'
        assert search(content, ["arm64-v8a"]) is None  # noqa: S101

    def test_empty_content(self) -> None:
        """Test with empty content."""
        assert search("", ["arm64-v8a"]) is None  # noqa: S101

    def test_multiple_matches(self) -> None:
        """Test that the first matching architecture is returned."""
        content = (
            '<p>x86</p><div class="v-report" data-file-id="111"></div>'
            '<p>arm64-v8a</p><div class="v-report" data-file-id="222"></div>'
        )
        # Search for x86 first
        assert search(content, ["x86"]) == "111"  # noqa: S101
        # Search for arm64-v8a
        assert search(content, ["arm64-v8a"]) == "222"  # noqa: S101
        # Search for both, x86 is first in document
        assert search(content, ["x86", "arm64-v8a"]) == "111"  # noqa: S101

    def test_whitespace_handling_strict(self) -> None:
        """Document strict whitespace behavior."""
        # Current implementation assumes no whitespace between <p> and <div>
        content = '<p>arm64-v8a</p> <div class="v-report" data-file-id="12345"></div>'
        assert search(content, ["arm64-v8a"]) is None  # noqa: S101


if __name__ == "__main__":
    unittest.main()
