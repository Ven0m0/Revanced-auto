#!/usr/bin/env python3
import argparse
import sys

try:
    from lxml import html
except ImportError:
    # If lxml is not available, we can't run.
    # The environment check should have ensured this, but let's be safe.
    print(
        "Error: lxml not installed. Install with: pip install lxml cssselect",
        file=sys.stderr,
    )
    sys.exit(1)


def get_allowed_archs(arch):
    base = ["universal", "noarch", "arm64-v8a + armeabi-v7a"]
    if arch == "all":
        return base
    return [arch, *base]


def process_row(row, apk_bundle, dpi, allowed_archs):
    # Mimic the bash logic: remove span:nth-child(n+3)
    # logic: "$HTMLQ" "div.table-row.headerFont" -r "span:nth-child(n+3)"
    spans = row.cssselect("span:nth-child(n+3)")
    for span in spans:
        span.drop_tree()

    # Extract all text nodes, stripped and non-empty
    texts = [t.strip() for t in row.xpath(".//text()") if t.strip()]

    # We need at least 6 items to check index 5 (6th item)
    if len(texts) < 6:
        return None

    # Indices based on:
    # Line 3 (index 2): apk_bundle
    # Line 4 (index 3): arch
    # Line 6 (index 5): dpi

    curr_bundle = texts[2]
    curr_arch = texts[3]
    curr_dpi = texts[5]

    if curr_bundle == apk_bundle and curr_dpi == dpi and curr_arch in allowed_archs:
        # dlurl=$(scrape_attr "div:nth-child(1) > a:nth-child(1)" href ...)
        link = row.cssselect("div:nth-child(1) > a:nth-child(1)")
        if link:
            href = link[0].get("href")
            if href:
                # Ensure we handle base URL
                if href.startswith("http"):
                    return href
                return "https://www.apkmirror.com" + href

    return None


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Search APKMirror HTML from stdin for a matching APK variant "
            "and print its download URL."
        )
    )
    parser.add_argument("--apk-bundle", required=True)
    parser.add_argument("--dpi", required=True)
    parser.add_argument("--arch", required=True)
    args = parser.parse_args()

    # Read from stdin
    try:
        html_content = sys.stdin.read()
    except KeyboardInterrupt:
        sys.exit(130)

    if not html_content:
        sys.exit(1)

    try:
        tree = html.fromstring(html_content)
    except Exception:
        sys.exit(1)

    allowed_archs = get_allowed_archs(args.arch)

    # Find all rows
    rows = tree.cssselect("div.table-row.headerFont")

    for row in rows:
        url = process_row(row, args.apk_bundle, args.dpi, allowed_archs)
        if url:
            print(url)
            sys.exit(0)

    # Not found
    sys.exit(1)


if __name__ == "__main__":
    main()
