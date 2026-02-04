#!/usr/bin/env python3
"""
Uptodown Search Script for ReVanced Builder

Parses Uptodown version file list HTML and searches for a compatible architecture.
Replaces the inefficient Bash loop that spawned multiple Python processes.
"""

import argparse
import sys

try:
    from lxml import html
except ImportError:
    print(
        "Error: lxml not installed. Install with: pip install lxml cssselect",
        file=sys.stderr,
    )
    sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="Search Uptodown HTML content for matching architecture"
    )
    parser.add_argument("archs", nargs="+", help="Allowed architecture strings")
    args = parser.parse_args()

    try:
        content = sys.stdin.read()
    except KeyboardInterrupt:
        sys.exit(130)

    if not content:
        sys.exit(1)

    # Wrap content in a div to ensure a single root element
    # The input is usually a list of sibling elements (p, div, p, div...)
    wrapped_content = f"<div>{content}</div>"

    try:
        tree = html.fromstring(wrapped_content)
    except html.etree.XMLSyntaxError:
        sys.exit(1)

    children = list(tree)

    # Iterate through children to find matching architecture
    # The structure is typically: <p>Arch Name</p> <div class="variant">...</div>
    allowed_archs = set(args.archs)

    # Iterate through adjacent pairs of elements (p, div).
    for p_elem, variant_div in zip(children, children[1:]):
        if p_elem.tag == "p":
            arch_text = p_elem.text_content().strip()

            if arch_text in allowed_archs:
                # Found a matching architecture, get file ID from the next element.
                v_reports = variant_div.cssselect(".v-report")
                if v_reports:
                    file_id = v_reports[0].get("data-file-id")
                    if file_id:
                        print(file_id)
                        sys.exit(0)

    # No matching architecture found
    sys.exit(1)


if __name__ == "__main__":
    main()
