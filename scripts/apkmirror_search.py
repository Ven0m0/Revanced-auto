#!/usr/bin/env python3
"""APKMirror Search Parser.

Optimized replacement for bash-based HTML parsing loop.
Extracts download URL for a specific APK variant from APKMirror release page.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from enum import Enum
from typing import Literal, TypeVar

from selectolax.parser import HTMLParser, Node

T = TypeVar("T")

# Type aliases
type ArchType = Literal["universal", "noarch", "arm64-v8a", "armeabi-v7a", "arm64-v8a + armeabi-v7a"]
type RowTextNodes = list[str]

# Constants
_MIN_ROW_FIELDS: int = 6  # version, size, bundle, arch, android_ver, dpi


class ArchStrategy(Enum):
    """Architecture matching strategy."""

    ALL = "all"
    SPECIFIC = "specific"


@dataclass(frozen=True, slots=True)
class SearchConfig:
    """Configuration for APKMirror search.

    Attributes:
        apk_bundle: Bundle type ("APK" or "BUNDLE").
        dpi: Screen DPI (e.g., "nodpi").
        arch: Target architecture.

    """

    apk_bundle: str
    dpi: str
    arch: str


@dataclass(frozen=True, slots=True)
class SearchResult:
    """Result of an APKMirror search operation.

    Attributes:
        found: Whether a matching APK was found.
        url: The download URL if found, None otherwise.
        reason: Explanation for the result.

    """

    found: bool
    url: str | None
    reason: str


@dataclass(frozen=True, slots=True)
class RowData:
    """Structured data extracted from a table row.

    Attributes:
        version: APK version string.
        size: File size string.
        bundle: Bundle type.
        arch: Architecture string.
        android_ver: Minimum Android version.
        dpi: Screen DPI.

    """

    version: str
    size: str
    bundle: str
    arch: str
    android_ver: str
    dpi: str


def get_target_archs(arch: str) -> list[str]:
    """Get list of compatible architectures based on requested arch.

    Args:
        arch: Requested architecture string.

    Returns:
        Ordered list of acceptable architectures including fallbacks.

    """
    base_archs: list[str] = ["universal", "noarch", "arm64-v8a + armeabi-v7a"]

    match arch:
        case "all":
            return base_archs
        case _:
            return [arch, *base_archs]


def is_valid_row_node(node: object) -> bool:
    """TypeGuard to validate a node is a valid selectolax Node.

    Args:
        node: Object to validate.

    Returns:
        True if node is a valid Node.

    """
    return isinstance(node, Node)


def _row_text_nodes(row: Node) -> RowTextNodes:
    """Extract ordered text nodes from a table row, replicating lxml itertext().

    Args:
        row: selectolax Node for the table row.

    Returns:
        List of stripped, non-empty text strings in document order.

    """
    texts: RowTextNodes = []
    for node in row.css("*"):
        t = node.text(deep=False)
        if t and (s := t.strip()):
            texts.append(s)
    return texts


def parse_row_data(text_nodes: RowTextNodes) -> RowData | None:
    """Parse row text nodes into structured RowData.

    Args:
        text_nodes: List of text strings from the row.

    Returns:
        RowData if enough fields are present, None otherwise.

    """
    if len(text_nodes) < _MIN_ROW_FIELDS:
        return None

    return RowData(
        version=text_nodes[0],
        size=text_nodes[1],
        bundle=text_nodes[2],
        arch=text_nodes[3],
        android_ver=text_nodes[4],
        dpi=text_nodes[5],
    )


def row_matches(row_data: RowData, config: SearchConfig, target_archs: list[str]) -> bool:
    """Check if a row matches the search configuration.

    Args:
        row_data: Structured row data.
        config: Search configuration.
        target_archs: List of acceptable architectures.

    Returns:
        True if the row matches all criteria.

    """
    return row_data.bundle == config.apk_bundle and row_data.dpi == config.dpi and row_data.arch in target_archs


def extract_download_url(row: Node) -> str | None:
    """Extract the download URL from a matching row.

    Args:
        row: The matching table row node.

    Returns:
        The full download URL if found, None otherwise.

    """
    link = row.css_first("div > a")
    if link is None:
        return None

    href = link.attrs.get("href")
    if not href:
        return None

    return f"https://www.apkmirror.com{href}"


def _parse_rows(tree: HTMLParser) -> list[Node]:
    """Parse all table rows from the HTML tree.

    Args:
        tree: Parsed HTML tree.

    Returns:
        List of row nodes matching the expected structure.

    """
    return tree.css("div.table-row.headerFont")


def search(html_content: str, config: SearchConfig) -> SearchResult:
    """Search for matching APK variant in HTML content.

    Args:
        html_content: HTML string from APKMirror release page.
        config: Search configuration.

    Returns:
        SearchResult with status, URL if found, and reason.

    """
    tree = HTMLParser(html_content)
    rows = _parse_rows(tree)

    if not rows:
        return SearchResult(found=False, url=None, reason="no_table_found")

    target_archs = get_target_archs(config.arch)

    for row in rows:
        if not is_valid_row_node(row):
            continue

        text_nodes = _row_text_nodes(row)
        row_data = parse_row_data(text_nodes)

        if row_data is None:
            continue

        if not row_matches(row_data, config, target_archs):
            continue

        url = extract_download_url(row)
        if url:
            return SearchResult(found=True, url=url, reason="found")

    return SearchResult(found=False, url=None, reason="no_match_in_table")


def main() -> int:
    """CLI entry point.

    Returns:
        Exit code: 0 if found, 1 if table found but no match, 2 if no table found.

    """
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
        return 130

    if not html_content:
        return 2

    config = SearchConfig(apk_bundle=args.apk_bundle, dpi=args.dpi, arch=args.arch)
    result = search(html_content, config)

    if result.found and result.url:
        print(result.url)
        return 0

    # Map result reasons to exit codes
    match result.reason:
        case "no_table_found":
            return 2
        case "no_match_in_table":
            return 1
        case _:
            return 1


if __name__ == "__main__":
    sys.exit(main())
