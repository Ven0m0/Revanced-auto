#!/usr/bin/env python3
"""
HTML Parser for ReVanced Builder
Replaces htmlq binary with Python-based HTML parsing using lxml.
Provides equivalent functionality for CSS selector-based text and attribute extraction.
Usage:
    # Extract text content
    cat page.html | python3 html_parser.py --text "div.class"
    # Extract attribute value
    cat page.html | python3 html_parser.py --attribute href "a.download"
    # Multiple matches (one per line)
    cat page.html | python3 html_parser.py --text "span.version"
Requirements:
    pip install lxml cssselect
Author: ReVanced Builder
License: Same as parent project
"""
import argparse
import sys
try:
    from lxml import etree, html
except ImportError:
    print(
        "Error: lxml not installed. Install with: pip install lxml cssselect",
        file=sys.stderr,
    )
    sys.exit(1)
def parse_html(html_content: str) -> html.HtmlElement:
    """
    Parse HTML content into an lxml tree.
    Args:
        html_content: Raw HTML string
    Returns:
        Parsed HTML tree
    Raises:
        etree.ParseError: If HTML is malformed
    """
    try:
        return html.fromstring(html_content)
    except etree.ParseError as e:
        print(f"Error parsing HTML: {e}", file=sys.stderr)
        sys.exit(1)
def scrape_text(tree: html.HtmlElement, selector: str) -> list[str]:
    """
    Extract text content from elements matching CSS selector.
    Args:
        tree: Parsed HTML tree
        selector: CSS selector string
    Returns:
        List of text content from matching elements
    """
    try:
        elements = tree.cssselect(selector)
        results = []
        for element in elements:
            # Get text content, stripping whitespace
            text = element.text_content().strip()
            if text:
                results.append(text)
        return results
    except Exception as e:
        print(f"Error with selector '{selector}': {e}", file=sys.stderr)
        sys.exit(1)
def scrape_attribute(tree: html.HtmlElement, selector: str, attribute: str) -> list[str]:
    """
    Extract attribute values from elements matching CSS selector.
    Args:
        tree: Parsed HTML tree
        selector: CSS selector string
        attribute: Attribute name to extract
    Returns:
        List of attribute values from matching elements
    """
    try:
        elements = tree.cssselect(selector)
        results = []
        for element in elements:
            # Get attribute value
            value = element.get(attribute)
            if value is not None:
                results.append(value.strip())
        return results
    except Exception as e:
        print(
            f"Error with selector '{selector}' or attribute '{attribute}': {e}",
            file=sys.stderr,
        )
        sys.exit(1)
def main() -> None:
    """
    Main entry point for HTML parser CLI.
    """
    parser = argparse.ArgumentParser(
        description="Parse HTML and extract text or attributes using CSS selectors",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("selector", help="CSS selector to match elements")
    parser.add_argument(
        "--text",
        action="store_true",
        help="Extract text content from matching elements",
    )
    parser.add_argument(
        "--attribute",
        metavar="ATTR",
        help="Extract attribute value from matching elements",
    )
    args = parser.parse_args()
    # Validate arguments
    if not args.text and not args.attribute:
        print("Error: Must specify either --text or --attribute", file=sys.stderr)
        sys.exit(1)
    if args.text and args.attribute:
        print("Error: Cannot use both --text and --attribute", file=sys.stderr)
        sys.exit(1)
    # Read HTML from stdin
    try:
        html_content = sys.stdin.read()
    except KeyboardInterrupt:
        sys.exit(130)
    if not html_content:
        print("Error: No HTML content received from stdin", file=sys.stderr)
        sys.exit(1)
    # Parse HTML
    tree = parse_html(html_content)
    # Extract data based on mode
    if args.text:
        results = scrape_text(tree, args.selector)
    else:
        results = scrape_attribute(tree, args.selector, args.attribute)
    # Output results (one per line, matching htmlq behavior)
    for result in results:
        print(result)
    # Exit with appropriate code
    sys.exit(0 if results else 1)
if __name__ == "__main__":
    main()
