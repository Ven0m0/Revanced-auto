#!/usr/bin/env python3
"""Uptodown Search Script for ReVanced Builder.

Parses Uptodown version file list HTML and searches for a compatible architecture.
Replaces the inefficient Bash loop that spawned multiple Python processes.
"""

import argparse
import sys

from selectolax.parser import HTMLParser


def search(content: str, allowed_archs_list: list[str]) -> str | None:
    """Search for a matching architecture in the HTML content.

    Args:
        content: The HTML content to search (usually a list of sibling elements).
        allowed_archs_list: A list of allowed architecture strings.

    Returns:
        The file ID if a match is found, otherwise None.
    """
    if not content:
        return None

    # Wrap siblings in a single root for reliable parsing
    tree = HTMLParser(f"<div>{content}</div>")
    root = tree.css_first("div")
    if root is None:
        return None

    allowed_archs = set(allowed_archs_list)

    for p in root.css("p"):
        arch = p.text(deep=True, strip=True)
        if arch not in allowed_archs:
            continue
        # The variant div immediately follows the <p> arch label
        next_sib = p.next
        if next_sib is None:
            continue
        v_report = next_sib.css_first(".v-report")
        if v_report is None:
            continue
        file_id = v_report.attrs.get("data-file-id")
        if file_id:
            return file_id

    return None


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Search Uptodown HTML content for matching architecture",
    )
    parser.add_argument("archs", nargs="+", help="Allowed architecture strings")
    args = parser.parse_args()

    try:
        content = sys.stdin.read()
    except KeyboardInterrupt:
        sys.exit(130)

    result = None if not content else search(content, args.archs)

    if result:
        print(result)
        sys.exit(0)

    sys.exit(1)


if __name__ == "__main__":
    main()
