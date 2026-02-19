#!/usr/bin/env python3
"""Uptodown Search Script for ReVanced Builder.

Parses Uptodown version file list HTML and searches for a compatible architecture.
Replaces the inefficient Bash loop that spawned multiple Python processes.
"""

import argparse
import sys

from selectolax.parser import HTMLParser


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

    if not content:
        sys.exit(1)

    # Wrap siblings in a single root for reliable parsing
    tree = HTMLParser(f"<div>{content}</div>")
    root = tree.css_first("div")
    if root is None:
        sys.exit(1)

    allowed_archs = set(args.archs)

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
            print(file_id)
            sys.exit(0)

    sys.exit(1)


if __name__ == "__main__":
    main()
