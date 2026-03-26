#!/usr/bin/env python3
"""Uptodown Search Script for ReVanced Builder.

Parses Uptodown version file list HTML and searches for a compatible architecture.
Replaces the inefficient Bash loop that spawned multiple Python processes.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from typing import Final

from selectolax.parser import HTMLParser, Node

# Type aliases
type FileId = str
type ArchSet = frozenset[str]

# HTML wrapper for reliable parsing
_WRAPPER_TAG: Final[str] = "div"
_WRAPPER_OPEN: Final[str] = f"<{_WRAPPER_TAG}>"
_WRAPPER_CLOSE: Final[str] = f"</{_WRAPPER_TAG}>"


@dataclass(frozen=True, slots=True)
class SearchConfig:
    """Configuration for architecture search.

    Attributes:
        allowed_archs: Set of acceptable architecture strings.

    """

    allowed_archs: ArchSet

    @classmethod
    def from_list(cls, archs: list[str]) -> SearchConfig:
        """Create config from list of architecture strings.

        Args:
            archs: List of acceptable architectures.

        Returns:
            SearchConfig instance.

        """
        return cls(allowed_archs=frozenset(archs))


@dataclass(frozen=True, slots=True)
class SearchResult:
    """Result of architecture search.

    Attributes:
        file_id: File ID if match found, None otherwise.
        arch_matched: Architecture that matched, None if no match.

    """

    file_id: FileId | None
    arch_matched: str | None

    @property
    def found(self) -> bool:
        """Return True if a match was found."""
        return self.file_id is not None


def is_valid_file_id(value: object) -> bool:
    """TypeGuard to validate a file ID value.

    Args:
        value: Object to validate.

    Returns:
        True if value is a non-empty string.

    """
    return isinstance(value, str) and len(value) > 0


def is_v_report_node(node: object) -> bool:
    """TypeGuard to validate a v-report node.

    Args:
        node: Object to validate.

    Returns:
        True if node is a valid Node with v-report class.

    """
    return isinstance(node, Node) and "v-report" in (node.attrs.get("class") or "")


def _parse_content(html_content: str) -> Node | None:
    """Parse HTML content and return the root node.

    Args:
        html_content: HTML content to parse (usually siblings without root).

    Returns:
        Root node if parsing succeeds, None otherwise.

    """
    if not html_content:
        return None

    # Wrap siblings in a single root for reliable parsing
    wrapped = f"{_WRAPPER_OPEN}{html_content}{_WRAPPER_CLOSE}"
    tree = HTMLParser(wrapped)
    return tree.css_first(_WRAPPER_TAG)


def _extract_file_id(node: Node) -> FileId | None:
    """Extract file ID from a v-report node.

    Args:
        node: The v-report node.

    Returns:
        File ID if found and valid, None otherwise.

    """
    file_id = node.attrs.get("data-file-id")
    return file_id if is_valid_file_id(file_id) else None


def _find_match(root: Node, config: SearchConfig) -> SearchResult:
    """Search for matching architecture in parsed HTML.

    Args:
        root: Root node containing architecture elements.
        config: Search configuration.

    Returns:
        SearchResult with file ID and matched architecture.

    """
    for p in root.css("p"):
        arch = p.text(deep=True, strip=True)
        if arch not in config.allowed_archs:
            continue

        # The variant div immediately follows the <p> arch label
        next_sib = p.next
        if next_sib is None:
            continue

        v_report = next_sib.css_first(".v-report")
        if v_report is None:
            continue

        file_id = _extract_file_id(v_report)
        if file_id:
            return SearchResult(file_id=file_id, arch_matched=arch)

    return SearchResult(file_id=None, arch_matched=None)


def search(html_content: str, config: SearchConfig) -> SearchResult:
    """Search for a matching architecture in the HTML content.

    Args:
        html_content: The HTML content to search (usually siblings without root).
        config: Search configuration with allowed architectures.

    Returns:
        SearchResult with file ID if found, or None values.

    """
    root = _parse_content(html_content)
    if root is None:
        return SearchResult(file_id=None, arch_matched=None)

    return _find_match(root, config)


def main() -> int:
    """CLI entry point.

    Returns:
        Exit code: 0 if match found, 1 otherwise, 130 on interrupt.

    """
    parser = argparse.ArgumentParser(
        description="Search Uptodown HTML content for matching architecture",
    )
    parser.add_argument("archs", nargs="+", help="Allowed architecture strings")
    args = parser.parse_args()

    try:
        content = sys.stdin.read()
    except KeyboardInterrupt:
        return 130

    config = SearchConfig.from_list(args.archs)
    result = search(content, config)

    if result.found:
        print(result.file_id)
        return 0

    return 1


if __name__ == "__main__":
    sys.exit(main())
