#!/usr/bin/env python3
"""HTML Parser for ReVanced Builder.

Replaces htmlq binary with Python-based HTML parsing using selectolax.
Provides CSS selector-based text and attribute extraction.

Usage:
    cat page.html | python3 html_parser.py --text "div.class"
    cat page.html | python3 html_parser.py --attribute href "a.download"
    cat page.html | python3 html_parser.py --text "span.version"
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from enum import Enum, auto
from typing import Protocol

from selectolax.parser import HTMLParser


class OutputMode(Enum):
    """Output extraction mode."""

    TEXT = auto()
    ATTRIBUTE = auto()


@dataclass(frozen=True, slots=True)
class ParseConfig:
    """Configuration for HTML parsing.

    Attributes:
        selector: CSS selector string.
        mode: Output extraction mode.
        attribute: Attribute name (for ATTRIBUTE mode).

    """

    selector: str
    mode: OutputMode
    attribute: str | None = None


@dataclass(frozen=True, slots=True)
class ParseResult:
    """Result of HTML parsing.

    Attributes:
        values: Extracted values.
        selector: CSS selector used.
        mode: Extraction mode used.

    """

    values: list[str]
    selector: str
    mode: OutputMode

    def __bool__(self) -> bool:
        """Return True if any values were extracted."""
        return bool(self.values)


class ScraperError(Exception):
    """Exception raised for scraper errors."""


class Parser(Protocol):
    """Protocol for HTML parsers."""

    def parse(self, html_content: str) -> HTMLParser:
        """Parse HTML content into a tree.

        Args:
            html_content: Raw HTML string.

        Returns:
            Parsed HTML tree.

        """
        ...

    def extract_text(self, tree: HTMLParser, selector: str) -> list[str]:
        """Extract text from elements matching selector.

        Args:
            tree: Parsed HTML tree.
            selector: CSS selector.

        Returns:
            List of extracted text values.

        """
        ...

    def extract_attribute(self, tree: HTMLParser, selector: str, attribute: str) -> list[str]:
        """Extract attribute values from elements matching selector.

        Args:
            tree: Parsed HTML tree.
            selector: CSS selector.
            attribute: Attribute name.

        Returns:
            List of extracted attribute values.

        """
        ...


class SelectolaxParser:
    """Parser implementation using selectolax."""

    @staticmethod
    def parse(html_content: str) -> HTMLParser:
        """Parse HTML content into selectolax tree.

        Args:
            html_content: Raw HTML string.

        Returns:
            Parsed HTML tree.

        Raises:
            ScraperError: If HTML content is empty.

        """
        if not html_content:
            raise ScraperError("No HTML content provided")
        return HTMLParser(html_content)

    @staticmethod
    def extract_text(tree: HTMLParser, selector: str) -> list[str]:
        """Extract text content from elements matching a CSS selector.

        Args:
            tree: Parsed HTML tree.
            selector: CSS selector string.

        Returns:
            List of stripped text values from matching elements.

        Raises:
            ScraperError: If selector is invalid or parsing fails.

        """
        results: list[str] = []

        try:
            nodes = tree.css(selector)
        except Exception as e:
            raise ScraperError(f"Error with selector '{selector}': {e}") from e

        for node in nodes:
            text = node.text(deep=True, strip=True)
            if text:
                results.append(text)

        return results

    @staticmethod
    def extract_attribute(tree: HTMLParser, selector: str, attribute: str) -> list[str]:
        """Extract attribute values from elements matching a CSS selector.

        Args:
            tree: Parsed HTML tree.
            selector: CSS selector string.
            attribute: Attribute name to extract.

        Returns:
            List of attribute values from matching elements.

        Raises:
            ScraperError: If selector is invalid or parsing fails.

        """
        results: list[str] = []

        try:
            nodes = tree.css(selector)
        except Exception as e:
            raise ScraperError(
                f"Error with selector '{selector}' or attribute '{attribute}': {e}",
            ) from e

        for node in nodes:
            val = node.attrs.get(attribute)
            if val is not None:
                results.append(val.strip())

        return results


def parse_html(html_content: str, parser: Parser | None = None) -> HTMLParser:
    """Parse HTML content into a tree.

    Args:
        html_content: Raw HTML string.
        parser: Optional parser implementation (defaults to SelectolaxParser).

    Returns:
        Parsed HTML tree.

    Raises:
        ScraperError: If HTML content is empty or parsing fails.

    """
    p = parser or SelectolaxParser()
    return p.parse(html_content)


def scrape_text(tree: HTMLParser, selector: str, parser: Parser | None = None) -> list[str]:
    """Extract text content from elements matching a CSS selector.

    Args:
        tree: Parsed HTML tree.
        selector: CSS selector string.
        parser: Optional parser implementation (defaults to SelectolaxParser).

    Returns:
        List of stripped text values from matching elements.

    Raises:
        ScraperError: If selector is invalid or parsing fails.

    """
    p = parser or SelectolaxParser()
    return p.extract_text(tree, selector)


def scrape_attribute(
    tree: HTMLParser,
    selector: str,
    attribute: str,
    parser: Parser | None = None,
) -> list[str]:
    """Extract attribute values from elements matching a CSS selector.

    Args:
        tree: Parsed HTML tree.
        selector: CSS selector string.
        attribute: Attribute name to extract.
        parser: Optional parser implementation (defaults to SelectolaxParser).

    Returns:
        List of attribute values from matching elements.

    Raises:
        ScraperError: If selector is invalid or parsing fails.

    """
    p = parser or SelectolaxParser()
    return p.extract_attribute(tree, selector, attribute)


def main() -> int:
    """Main entry point for HTML parser CLI.

    Returns:
        Exit code: 0 if results found, 1 if no results or error, 130 on interrupt.

    """
    parser = argparse.ArgumentParser(
        description="Parse HTML and extract text or attributes using CSS selectors",
    )
    parser.add_argument("selector", help="CSS selector to match elements")
    parser.add_argument("--text", action="store_true", help="Extract text content")
    parser.add_argument("--attribute", metavar="ATTR", help="Extract attribute value")
    args = parser.parse_args()

    # Validate mode selection
    if not args.text and not args.attribute:
        print("Error: Must specify either --text or --attribute", file=sys.stderr)
        return 1
    if args.text and args.attribute:
        print("Error: Cannot use both --text and --attribute", file=sys.stderr)
        return 1

    # Build configuration
    mode = OutputMode.TEXT if args.text else OutputMode.ATTRIBUTE
    config = ParseConfig(
        selector=args.selector,
        mode=mode,
        attribute=args.attribute,
    )

    # Read input
    try:
        html_content = sys.stdin.read()
    except KeyboardInterrupt:
        return 130

    # Parse and extract
    try:
        tree = parse_html(html_content)

        match config.mode:
            case OutputMode.TEXT:
                results = scrape_text(tree, config.selector)
            case OutputMode.ATTRIBUTE:
                if config.attribute is None:
                    print("Error: --attribute requires a value", file=sys.stderr)
                    return 1
                results = scrape_attribute(tree, config.selector, config.attribute)

        for result in results:
            print(result)

        return 0 if results else 1

    except ScraperError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
