#!/usr/bin/env python3
"""APKMirror Search Parser.

Optimized replacement for bash-based HTML parsing loop.
Extracts download URL for a specific APK variant from APKMirror release page.
"""

import argparse
import sys

from selectolax.parser import HTMLParser, Node

_MIN_ROW_FIELDS = 6  # version, size, bundle, arch, android_ver, dpi
BASE_ARCHS = ["universal", "noarch", "arm64-v8a + armeabi-v7a"]


def get_target_archs(arch: str) -> list[str]:
    """Get list of compatible architectures based on requested arch.

    Args:
        arch: Requested architecture string.

    Returns:
        Ordered list of acceptable architectures including fallbacks.
    """
    if arch == "all":
        return BASE_ARCHS
    return [arch, *BASE_ARCHS]


def _row_text_nodes(row: Node) -> list[str]:
    """Extract ordered text nodes from a table row, replicating lxml itertext().

    Args:
        row: selectolax Node for the table row.

    Returns:
        List of stripped, non-empty text strings in document order.
    """
    texts: list[str] = []
    for node in row.css("*"):
        t = node.text(deep=False)
        if t and (s := t.strip()):
            texts.append(s)
    return texts


def search(html_content: str, apk_bundle: str, dpi: str, arch: str) -> int:
    """Search for matching APK variant in HTML content.

    Args:
        html_content: HTML string from APKMirror release page.
        apk_bundle: Bundle type ("APK" or "BUNDLE").
        dpi: Screen DPI (e.g., "nodpi").
        arch: Architecture (e.g., "arm64-v8a").

    Returns:
        0 if found, 1 if table found but no match, 2 if no table found.
    """
    tree = HTMLParser(html_content)
    rows = tree.css("div.table-row.headerFont")

    if not rows:
        return 2

    target_archs = get_target_archs(arch)

    for row in rows:
        text_nodes = _row_text_nodes(row)
        if len(text_nodes) < _MIN_ROW_FIELDS:
            continue

        if text_nodes[2] != apk_bundle:
            continue
        if text_nodes[5] != dpi:
            continue
        if text_nodes[3] not in target_archs:
            continue

        # div:first-child > a:first-child -> href
        link = row.css_first("div > a")
        if link:
            href = link.attrs.get("href")
            if href:
                print(f"https://www.apkmirror.com{href}")
                return 0

    return 1


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Search APKMirror release page for specific variant",
    )
    parser.add_argument("--apk-bundle", required=True, help="APK bundle type (APK or BUNDLE)")
    parser.add_argument("--dpi", required=True, help="Screen DPI")
    parser.add_argument("--arch", required=True, help="Architecture")
    args = parser.parse_args()

    try:
        html_content = sys.stdin.read()
    except KeyboardInterrupt:
        sys.exit(130)

    if not html_content:
        sys.exit(2)

    sys.exit(search(html_content, args.apk_bundle, args.dpi, args.arch))


if __name__ == "__main__":
    main()
