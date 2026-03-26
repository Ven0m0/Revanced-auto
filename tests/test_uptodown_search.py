"""Test suite for Uptodown search logic using pytest."""

from __future__ import annotations

import pytest

from scripts.uptodown_search import (
    SearchConfig,
    SearchResult,
    _parse_content,
    is_valid_file_id,
    search,
)


class TestSearchConfig:
    """Tests for SearchConfig dataclass."""

    def test_from_list_creates_frozenset(self) -> None:
        """Test that from_list creates frozenset of architectures."""
        config = SearchConfig.from_list(["arm64-v8a", "x86"])
        assert config.allowed_archs == frozenset(["arm64-v8a", "x86"])

    def test_empty_list_creates_empty_frozenset(self) -> None:
        """Test that empty list creates empty frozenset."""
        config = SearchConfig.from_list([])
        assert config.allowed_archs == frozenset()

    def test_duplicate_archs_removed(self) -> None:
        """Test that duplicate architectures are deduplicated."""
        config = SearchConfig.from_list(["arm64-v8a", "arm64-v8a", "x86"])
        assert config.allowed_archs == frozenset(["arm64-v8a", "x86"])


class TestSearchResult:
    """Tests for SearchResult dataclass."""

    def test_found_property_with_file_id(self) -> None:
        """Test found property is True when file_id exists."""
        result = SearchResult(file_id="12345", arch_matched="arm64-v8a")
        assert result.found is True

    def test_found_property_without_file_id(self) -> None:
        """Test found property is False when file_id is None."""
        result = SearchResult(file_id=None, arch_matched=None)
        assert result.found is False

    def test_found_property_with_none_file_id(self) -> None:
        """Test found property with explicit None."""
        result = SearchResult(file_id=None, arch_matched="arm64-v8a")
        assert result.found is False


class TestIsValidFileId:
    """Tests for is_valid_file_id TypeGuard."""

    def test_valid_string_returns_true(self) -> None:
        """Test valid file ID string returns True."""
        assert is_valid_file_id("12345") is True
        assert is_valid_file_id("abc123") is True

    def test_empty_string_returns_false(self) -> None:
        """Test empty string returns False."""
        assert is_valid_file_id("") is False

    def test_non_string_returns_false(self) -> None:
        """Test non-string values return False."""
        assert is_valid_file_id(None) is False
        assert is_valid_file_id(123) is False
        assert is_valid_file_id(["123"]) is False


class TestParseContent:
    """Tests for _parse_content function."""

    def test_valid_content_returns_node(self) -> None:
        """Test that valid HTML content returns a node."""
        content = '<p>test</p><div class="v-report" data-file-id="123"></div>'
        root = _parse_content(content)
        assert root is not None

    def test_empty_content_returns_none(self) -> None:
        """Test that empty content returns None."""
        root = _parse_content("")
        assert root is None

    def test_whitespace_content_returns_node(self) -> None:
        """Test that whitespace-only content returns a node (parsed as text)."""
        root = _parse_content("   \n  ")
        # Whitespace creates a text node, still returns a div wrapper
        assert root is not None


class TestSearch:
    """Tests for search function."""

    def test_match_found_basic(self) -> None:
        """Test basic match with direct sibling structure."""
        content = '<p>arm64-v8a</p><div class="v-report" data-file-id="12345"></div>'
        config = SearchConfig.from_list(["arm64-v8a"])
        result = search(content, config)

        assert result.found is True
        assert result.file_id == "12345"
        assert result.arch_matched == "arm64-v8a"

    def test_no_match_wrong_arch(self) -> None:
        """Test when architecture doesn't match allowed list."""
        content = '<p>armeabi-v7a</p><div class="v-report" data-file-id="12345"></div>'
        config = SearchConfig.from_list(["arm64-v8a"])
        result = search(content, config)

        assert result.found is False
        assert result.file_id is None
        assert result.arch_matched is None

    def test_no_match_missing_div(self) -> None:
        """Test when arch label exists but variant div is missing."""
        content = "<p>arm64-v8a</p>"
        config = SearchConfig.from_list(["arm64-v8a"])
        result = search(content, config)

        assert result.found is False

    def test_no_match_missing_file_id(self) -> None:
        """Test when div exists but no data-file-id attribute."""
        content = '<p>arm64-v8a</p><div class="v-report"></div>'
        config = SearchConfig.from_list(["arm64-v8a"])
        result = search(content, config)

        assert result.found is False

    def test_empty_content_returns_not_found(self) -> None:
        """Test with empty content returns not found."""
        config = SearchConfig.from_list(["arm64-v8a"])
        result = search("", config)

        assert result.found is False

    def test_first_match_returned(self) -> None:
        """Test that the first matching architecture is returned."""
        content = (
            '<p>x86</p><div class="v-report" data-file-id="111"></div>'
            '<p>arm64-v8a</p><div class="v-report" data-file-id="222"></div>'
        )
        # Search for x86 first
        config = SearchConfig.from_list(["x86"])
        result = search(content, config)
        assert result.file_id == "111"

        # Search for arm64-v8a
        config = SearchConfig.from_list(["arm64-v8a"])
        result = search(content, config)
        assert result.file_id == "222"

        # Search for both, x86 is first in document
        config = SearchConfig.from_list(["x86", "arm64-v8a"])
        result = search(content, config)
        assert result.file_id == "111"

    def test_whitespace_handling(self) -> None:
        """Document strict whitespace behavior - whitespace breaks sibling detection."""
        # Current implementation assumes no whitespace between <p> and <div>
        content = '<p>arm64-v8a</p> <div class="v-report" data-file-id="12345"></div>'
        config = SearchConfig.from_list(["arm64-v8a"])
        result = search(content, config)

        # Due to text node being the next sibling, this returns not found
        assert result.found is False


@pytest.mark.parametrize(
    ("archs", "expected_file_id"),
    [
        (["arm64-v8a"], "12345"),
        (["x86"], "11111"),
        (["arm64-v8a", "x86"], "12345"),  # First match wins
    ],
)
def test_parametrized_arch_matching(
    sample_uptodown_html: str,
    archs: list[str],
    expected_file_id: str,
) -> None:
    """Test architecture matching with various inputs."""
    config = SearchConfig.from_list(archs)
    result = search(sample_uptodown_html, config)
    assert result.file_id == expected_file_id


@pytest.mark.parametrize(
    "arch",
    [
        "arm64-v8a",
        "armeabi-v7a",
        "x86",
        "x86_64",
        "universal",
    ],
)
def test_various_architectures_supported(arch: str) -> None:
    """Test that various architecture strings can be searched."""
    content = f'<p>{arch}</p><div class="v-report" data-file-id="12345"></div>'
    config = SearchConfig.from_list([arch])
    result = search(content, config)
    assert result.found is True
    assert result.file_id == "12345"
