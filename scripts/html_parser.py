#!/usr/bin/env python3
"""HTML Parser for ReVanced Builder.

Replaces htmlq binary with Python-based HTML parsing using selectolax.
Provides CSS selector-based text and attribute extraction.

Usage:
    cat page.html | python3 html_parser.py --text "div.class"
    cat page.html | python3 html_parser.py --attribute href "a.download"
    cat page.html | python3 html_parser.py --text "span.version"
"""

import argparse
import sys

from selectolax.parser import HTMLParser


def scrape_text(tree: HTMLParser, selector: str) -> list[str]:
    """Extract text content from elements matching a CSS selector.

    Args:
        tree: Parsed HTML tree.
        selector: CSS selector string.

    Returns:
        List of stripped text values from matching elements.
    """
    results = []
    try:
        for node in tree.css(selector):
            text = node.text(deep=True, strip=True)
            if text:
                results.append(text)
    except Exception as e:
        print(f"Error with selector '{selector}': {e}", file=sys.stderr)
        sys.exit(1)
    return results


def scrape_attribute(tree: HTMLParser, selector: str, attribute: str) -> list[str]:
    """Extract attribute values from elements matching a CSS selector.

    Args:
        tree: Parsed HTML tree.
        selector: CSS selector string.
        attribute: Attribute name to extract.

    Returns:
        List of attribute values from matching elements.
    """
    results = []
    try:
        for node in tree.css(selector):
            val = node.attrs.get(attribute)
            if val is not None:
                results.append(val.strip())
    except Exception as e:
        print(f"Error with selector '{selector}' or attribute '{attribute}': {e}", file=sys.stderr)
        sys.exit(1)
    return results


def main() -> None:
    """Main entry point for HTML parser CLI."""
    parser = argparse.ArgumentParser(
        description="Parse HTML and extract text or attributes using CSS selectors",
    )
    parser.add_argument("selector", help="CSS selector to match elements")
    parser.add_argument("--text", action="store_true", help="Extract text content")
    parser.add_argument("--attribute", metavar="ATTR", help="Extract attribute value")
    args = parser.parse_args()

    if not args.text and not args.attribute:
        print("Error: Must specify either --text or --attribute", file=sys.stderr)
        sys.exit(1)
    if args.text and args.attribute:
        print("Error: Cannot use both --text and --attribute", file=sys.stderr)
        sys.exit(1)

    try:
        html_content = sys.stdin.read()
    except KeyboardInterrupt:
        sys.exit(130)

    if not html_content:
        print("Error: No HTML content received from stdin", file=sys.stderr)
        sys.exit(1)

    tree = HTMLParser(html_content)

    if args.text:
        results = scrape_text(tree, args.selector)
    else:
        results = scrape_attribute(tree, args.selector, args.attribute)

    for result in results:
        print(result)

    sys.exit(0 if results else 1)


if __name__ == "__main__":
    main()
