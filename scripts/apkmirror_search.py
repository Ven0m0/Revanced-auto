#!/usr/bin/env python3
"""
APKMirror Search Parser

Optimized replacement for bash-based HTML parsing loop.
Extracts download URL for a specific APK variant from APKMirror release page.
"""

import argparse
import sys

try:
    from lxml import html
    from lxml.etree import LxmlError
except ImportError:
    print("Error: lxml not installed", file=sys.stderr)
    sys.exit(1)


def get_target_archs(arch: str) -> list[str]:
    """
    Get list of compatible architectures based on requested arch.
    Matches logic in scripts/lib/download.sh
    """
    # Base fallback architectures
    base_archs = ["universal", "noarch", "arm64-v8a + armeabi-v7a"]

    if arch == "all":
        return base_archs

    # Prepend requested arch to fallbacks
    return [arch, *base_archs]


def search(html_content: str, apk_bundle: str, dpi: str, arch: str) -> int:
    """
    Search for matching APK variant in HTML content.
    Prints download URL to stdout on success.

    Args:
        html_content: HTML string
        apk_bundle: Bundle type ("APK" or "BUNDLE")
        dpi: Screen DPI (e.g., "nodpi")
        arch: Architecture (e.g., "arm64-v8a")

    Returns:
        0 if found
        1 if table found but no match
        2 if no table found (legacy fallback mode)
    """
    try:
        tree = html.fromstring(html_content)
    except Exception as e:
        print(f"Error parsing HTML: {e}", file=sys.stderr)
        return 1  # Treat parse error as failure

    # Use XPath instead of cssselect to avoid dependency on cssselect package
    # Select div elements with class "table-row" and "headerFont"
    rows = tree.xpath("//div[contains(@class, 'table-row') and contains(@class, 'headerFont')]")

    if not rows:
        return 2

    target_archs = get_target_archs(arch)

    for row in rows:
        # Extract all text nodes from the row, stripping whitespace
        # This matches the behavior of scrape_text in the bash script
        text_nodes = [t.strip() for t in row.itertext() if t.strip()]

        # We need at least 6 text nodes to check the conditions
        # Index mapping based on 'sed -n Np':
        # 3p -> index 2 (Bundle type)
        # 4p -> index 3 (Architecture)
        # 6p -> index 5 (DPI)
        if len(text_nodes) < 6:
            continue

        row_bundle = text_nodes[2]
        row_arch = text_nodes[3]
        row_dpi = text_nodes[5]

        # Check conditions
        if row_bundle != apk_bundle:
            continue

        if row_dpi != dpi:
            continue

        if row_arch not in target_archs:
            continue

        # Extract download URL
        # Logic: div:nth-child(1) > a:nth-child(1) -> href
        # XPath: ./div[1]/a[1]
        links = row.xpath("./div[1]/a[1]")
        if links:
            href = links[0].get("href")
            if href:
                # Base URL is https://www.apkmirror.com
                print(f"https://www.apkmirror.com{href}")
                return 0

    return 1


def main():
    parser = argparse.ArgumentParser(
        description="Search APKMirror release page for specific variant"
    )
    parser.add_argument("--apk-bundle", required=True, help="APK bundle type (APK or BUNDLE)")
    parser.add_argument("--dpi", required=True, help="Screen DPI")
    parser.add_argument("--arch", required=True, help="Architecture")

    args = parser.parse_args()

    # Read HTML from stdin
    try:
        html_content = sys.stdin.read()
    except KeyboardInterrupt:
        sys.exit(130)

    if not html_content:
        # Treat empty input as "no table found" so it falls back
        sys.exit(2)

    sys.exit(search(html_content, args.apk_bundle, args.dpi, args.arch))


if __name__ == "__main__":
    main()
