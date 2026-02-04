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
    except Exception:
        sys.exit(1)

    children = list(tree)

    # Iterate through children to find matching architecture
    # The structure is typically: <p>Arch Name</p> <div class="variant">...</div>
    i = 0
    while i < len(children) - 1:
        elem = children[i]

        # Look for <p> tags containing the architecture name
        if elem.tag == "p":
            arch_text = elem.text_content().strip()

            # Check if this architecture is in our allowed list
            if arch_text in args.archs:
                # The next element should be the variant div
                next_elem = children[i + 1]

                # Verify it's a div (optional but good for robustness)
                # and search for the data-file-id inside it
                # Selector used in bash: div.variant > .v-report

                # We search within the next element
                v_reports = next_elem.cssselect(".v-report")
                if v_reports:
                    file_id = v_reports[0].get("data-file-id")
                    if file_id:
                        print(file_id)
                        sys.exit(0)

        i += 1

    # No matching architecture found
    sys.exit(1)


if __name__ == "__main__":
    main()
