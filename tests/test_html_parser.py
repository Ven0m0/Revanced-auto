"""Test suite for HTML parser utility."""

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock

import pytest

# Add the project root to sys.path to ensure we can import scripts
sys.path.append(str(Path(__file__).resolve().parent.parent))

from selectolax.parser import HTMLParser

from scripts.html_parser import parse_html, scrape_attribute, scrape_text


class TestHtmlParser(unittest.TestCase):
    """Test suite for HTML parser utility."""

    def setUp(self) -> None:
        """Set up shared HTML fixture."""
        self.html_content = """
        <html>
            <body>
                <div class="content">
                    <p>Paragraph 1</p>
                    <p class="special">Paragraph 2</p>
                </div>
                <a href="https://example.com" class="link">Link 1</a>
                <a href="https://test.com" class="link" id="link2">Link 2</a>
                <div id="empty"></div>
                <div class="nested">
                    <span>Nested Text</span>
                </div>
            </body>
        </html>
        """
        self.tree = parse_html(self.html_content)

    def test_parse_html_valid(self) -> None:
        """Test parsing valid HTML."""
        tree = parse_html("<div>test</div>")
        assert isinstance(tree, HTMLParser)  # noqa: S101
        assert tree.body.child.text() == "test"  # noqa: S101

    def test_parse_html_empty(self) -> None:
        """Test parsing empty HTML raises ValueError."""
        with pytest.raises(ValueError, match="No HTML content provided"):
            parse_html("")

    def test_scrape_text_valid(self) -> None:
        """Test scraping text with valid selector."""
        results = scrape_text(self.tree, "p.special")
        assert results == ["Paragraph 2"]  # noqa: S101

    def test_scrape_text_multiple(self) -> None:
        """Test scraping text with multiple matches."""
        results = scrape_text(self.tree, "p")
        assert results == ["Paragraph 1", "Paragraph 2"]  # noqa: S101

    def test_scrape_text_nested(self) -> None:
        """Test scraping nested text."""
        results = scrape_text(self.tree, "div.nested")
        assert results == ["Nested Text"]  # noqa: S101

    def test_scrape_text_no_match(self) -> None:
        """Test scraping text with no matches returns empty list."""
        results = scrape_text(self.tree, "div.nonexistent")
        assert results == []  # noqa: S101

    def test_scrape_text_exception(self) -> None:
        """Test scraping text handles exceptions by raising ValueError."""
        mock_tree = MagicMock(spec=HTMLParser)
        mock_tree.css.side_effect = Exception("Simulated error")

        with pytest.raises(ValueError, match="Error with selector 'div': Simulated error"):
            scrape_text(mock_tree, "div")

    def test_scrape_attribute_valid(self) -> None:
        """Test scraping attribute with valid selector."""
        results = scrape_attribute(self.tree, "a#link2", "href")
        assert results == ["https://test.com"]  # noqa: S101

    def test_scrape_attribute_multiple(self) -> None:
        """Test scraping attribute with multiple matches."""
        results = scrape_attribute(self.tree, "a.link", "href")
        assert results == ["https://example.com", "https://test.com"]  # noqa: S101

    def test_scrape_attribute_missing_attr(self) -> None:
        """Test scraping attribute where some elements miss the attribute."""
        results = scrape_attribute(self.tree, "a.link", "id")
        assert results == ["link2"]  # noqa: S101

    def test_scrape_attribute_no_match(self) -> None:
        """Test scraping attribute with no matches returns empty list."""
        results = scrape_attribute(self.tree, "a.nonexistent", "href")
        assert results == []  # noqa: S101

    def test_scrape_attribute_exception(self) -> None:
        """Test scraping attribute handles exceptions by raising ValueError."""
        mock_tree = MagicMock(spec=HTMLParser)
        mock_tree.css.side_effect = Exception("Simulated error")

        with pytest.raises(
            ValueError,
            match="Error with selector 'div' or attribute 'class': Simulated error",
        ):
            scrape_attribute(mock_tree, "div", "class")


if __name__ == "__main__":
    unittest.main()
