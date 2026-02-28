import unittest
import sys
import os
from unittest.mock import MagicMock, patch

# Ensure scripts module can be imported
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.html_parser import parse_html, scrape_text, scrape_attribute
from selectolax.parser import HTMLParser

class TestHtmlParser(unittest.TestCase):
    def setUp(self):
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

    def test_parse_html_valid(self):
        """Test parsing valid HTML."""
        tree = parse_html("<div>test</div>")
        self.assertIsInstance(tree, HTMLParser)
        self.assertEqual(tree.body.child.text(), "test")

    def test_parse_html_empty(self):
        """Test parsing empty HTML raises ValueError."""
        with self.assertRaises(ValueError):
            parse_html("")

    def test_scrape_text_valid(self):
        """Test scraping text with valid selector."""
        results = scrape_text(self.tree, "p.special")
        self.assertEqual(results, ["Paragraph 2"])

    def test_scrape_text_multiple(self):
        """Test scraping text with multiple matches."""
        results = scrape_text(self.tree, "p")
        self.assertEqual(results, ["Paragraph 1", "Paragraph 2"])

    def test_scrape_text_nested(self):
        """Test scraping nested text."""
        results = scrape_text(self.tree, "div.nested")
        self.assertEqual(results, ["Nested Text"])

    def test_scrape_text_no_match(self):
        """Test scraping text with no matches returns empty list."""
        results = scrape_text(self.tree, "div.nonexistent")
        self.assertEqual(results, [])

    def test_scrape_text_exception(self):
        """Test scraping text handles exceptions by raising ValueError."""
        # Mock tree.css to raise an exception
        mock_tree = MagicMock(spec=HTMLParser)
        mock_tree.css.side_effect = Exception("Simulated error")

        with self.assertRaises(ValueError) as cm:
            scrape_text(mock_tree, "div")
        self.assertIn("Error with selector 'div': Simulated error", str(cm.exception))

    def test_scrape_attribute_valid(self):
        """Test scraping attribute with valid selector."""
        results = scrape_attribute(self.tree, "a#link2", "href")
        self.assertEqual(results, ["https://test.com"])

    def test_scrape_attribute_multiple(self):
        """Test scraping attribute with multiple matches."""
        results = scrape_attribute(self.tree, "a.link", "href")
        self.assertEqual(results, ["https://example.com", "https://test.com"])

    def test_scrape_attribute_missing_attr(self):
        """Test scraping attribute where some elements miss the attribute."""
        # Link 1 doesn't have id, Link 2 does
        results = scrape_attribute(self.tree, "a.link", "id")
        self.assertEqual(results, ["link2"])

    def test_scrape_attribute_no_match(self):
        """Test scraping attribute with no matches returns empty list."""
        results = scrape_attribute(self.tree, "a.nonexistent", "href")
        self.assertEqual(results, [])

    def test_scrape_attribute_exception(self):
        """Test scraping attribute handles exceptions by raising ValueError."""
        # Mock tree.css to raise an exception
        mock_tree = MagicMock(spec=HTMLParser)
        mock_tree.css.side_effect = Exception("Simulated error")

        with self.assertRaises(ValueError) as cm:
            scrape_attribute(mock_tree, "div", "class")
        self.assertIn("Error with selector 'div' or attribute 'class': Simulated error", str(cm.exception))

if __name__ == "__main__":
    unittest.main()
