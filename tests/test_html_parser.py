"""Test suite for HTML parser utility using pytest."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from scripts.html_parser import (
    OutputMode,
    ParseConfig,
    ParseResult,
    ScraperError,
    SelectolaxParser,
    parse_html,
    scrape_attribute,
    scrape_text,
)


class TestParseHtml:
    """Tests for parse_html function."""

    def test_parse_valid_html(self) -> None:
        """Test parsing valid HTML returns HTMLParser."""
        tree = parse_html("<div>test</div>")
        assert isinstance(tree, SelectolaxParser().parse("<div>test</div>").__class__)

    def test_parse_empty_html_raises_error(self) -> None:
        """Test parsing empty HTML raises ScraperError."""
        with pytest.raises(ScraperError, match="No HTML content provided"):
            parse_html("")

    def test_parse_nested_html(self, sample_html_basic: str) -> None:
        """Test parsing nested HTML structure."""
        tree = parse_html(sample_html_basic)
        results = scrape_text(tree, "div.nested")
        assert results == ["Nested Text"]


class TestScrapeText:
    """Tests for scrape_text function."""

    def test_scrape_single_match(self, sample_html_basic: str) -> None:
        """Test scraping text with single match."""
        tree = parse_html(sample_html_basic)
        results = scrape_text(tree, "p.special")
        assert results == ["Paragraph 2"]

    def test_scrape_multiple_matches(self, sample_html_basic: str) -> None:
        """Test scraping text with multiple matches."""
        tree = parse_html(sample_html_basic)
        results = scrape_text(tree, "p")
        assert results == ["Paragraph 1", "Paragraph 2"]

    def test_scrape_no_match_returns_empty(self, sample_html_basic: str) -> None:
        """Test scraping with no matches returns empty list."""
        tree = parse_html(sample_html_basic)
        results = scrape_text(tree, "div.nonexistent")
        assert results == []

    def test_scrape_nested_content(self, sample_html_basic: str) -> None:
        """Test scraping nested text content."""
        tree = parse_html(sample_html_basic)
        results = scrape_text(tree, "div.nested")
        assert results == ["Nested Text"]

    def test_scrape_with_mock_error(self) -> None:
        """Test scrape_text handles parser errors."""
        mock_parser = MagicMock(spec=SelectolaxParser)
        mock_parser.extract_text.side_effect = ScraperError("Test error")
        tree = parse_html("<div>test</div>")

        with pytest.raises(ScraperError, match="Test error"):
            scrape_text(tree, "div", parser=mock_parser)


class TestScrapeAttribute:
    """Tests for scrape_attribute function."""

    def test_scrape_single_attribute(self, sample_html_basic: str) -> None:
        """Test scraping attribute from single matching element."""
        tree = parse_html(sample_html_basic)
        results = scrape_attribute(tree, "a#link2", "href")
        assert results == ["https://test.com"]

    def test_scrape_multiple_attributes(self, sample_html_basic: str) -> None:
        """Test scraping attribute from multiple matching elements."""
        tree = parse_html(sample_html_basic)
        results = scrape_attribute(tree, "a.link", "href")
        assert results == ["https://example.com", "https://test.com"]

    def test_scrape_missing_attribute_filtered(self, sample_html_basic: str) -> None:
        """Test that elements missing the attribute are filtered out."""
        tree = parse_html(sample_html_basic)
        results = scrape_attribute(tree, "a.link", "id")
        assert results == ["link2"]

    def test_scrape_no_match_returns_empty(self, sample_html_basic: str) -> None:
        """Test scraping attribute with no matching elements."""
        tree = parse_html(sample_html_basic)
        results = scrape_attribute(tree, "a.nonexistent", "href")
        assert results == []


class TestSelectolaxParser:
    """Tests for SelectolaxParser class."""

    def test_parse_valid_content(self) -> None:
        """Test parsing valid HTML content."""
        parser = SelectolaxParser()
        tree = parser.parse("<html><body>Test</body></html>")
        assert tree is not None

    def test_parse_empty_content_raises(self) -> None:
        """Test parsing empty content raises ScraperError."""
        parser = SelectolaxParser()
        with pytest.raises(ScraperError, match="No HTML content provided"):
            parser.parse("")

    def test_extract_text_basic(self) -> None:
        """Test basic text extraction."""
        parser = SelectolaxParser()
        tree = parser.parse("<div class='test'>Hello</div>")
        results = parser.extract_text(tree, ".test")
        assert results == ["Hello"]

    def test_extract_attribute_basic(self) -> None:
        """Test basic attribute extraction."""
        parser = SelectolaxParser()
        tree = parser.parse('<a href="https://example.com">Link</a>')
        results = parser.extract_attribute(tree, "a", "href")
        assert results == ["https://example.com"]


class TestParseResult:
    """Tests for ParseResult dataclass."""

    def test_parse_result_truthy_with_values(self) -> None:
        """Test ParseResult is truthy when it has values."""
        result = ParseResult(values=["a", "b"], selector="div", mode=OutputMode.TEXT)
        assert bool(result) is True
        assert result.values == ["a", "b"]

    def test_parse_result_falsy_empty(self) -> None:
        """Test ParseResult is falsy when empty."""
        result = ParseResult(values=[], selector="div", mode=OutputMode.TEXT)
        assert bool(result) is False


class TestParseConfig:
    """Tests for ParseConfig dataclass."""

    def test_config_creation(self) -> None:
        """Test creating ParseConfig."""
        config = ParseConfig(
            selector="div.content",
            mode=OutputMode.TEXT,
            attribute=None,
        )
        assert config.selector == "div.content"
        assert config.mode == OutputMode.TEXT
        assert config.attribute is None

    def test_config_with_attribute(self) -> None:
        """Test creating ParseConfig with attribute."""
        config = ParseConfig(
            selector="a.link",
            mode=OutputMode.ATTRIBUTE,
            attribute="href",
        )
        assert config.mode == OutputMode.ATTRIBUTE
        assert config.attribute == "href"


@pytest.mark.parametrize(
    ("selector", "expected_count", "first_result"),
    [
        ("p", 2, "Paragraph 1"),
        ("p.special", 1, "Paragraph 2"),
        ("div.content p", 2, "Paragraph 1"),
    ],
)
def test_parametrized_text_extraction(
    sample_html_basic: str,
    selector: str,
    expected_count: int,
    first_result: str,
) -> None:
    """Test text extraction with various selectors."""
    tree = parse_html(sample_html_basic)
    results = scrape_text(tree, selector)
    assert len(results) == expected_count
    assert results[0] == first_result


@pytest.mark.parametrize(
    ("selector", "attr", "expected"),
    [
        ("a.link", "href", ["https://example.com", "https://test.com"]),
        ("a#link2", "id", ["link2"]),
        ("div.content", "class", ["content"]),
    ],
)
def test_parametrized_attribute_extraction(
    sample_html_basic: str,
    selector: str,
    attr: str,
    expected: list[str],
) -> None:
    """Test attribute extraction with various selectors."""
    tree = parse_html(sample_html_basic)
    results = scrape_attribute(tree, selector, attr)
    assert results == expected
