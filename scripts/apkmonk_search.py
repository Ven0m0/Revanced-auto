#!/usr/bin/env python3
"""APKMonk version list and download-key parser.

Reads an APKMonk app page from stdin and outputs either:
  - A newline-separated list of available version strings (--versions)
  - The version-specific page URL for a given version (--version-url)
  - A ``pkg:key`` pair extracted from a version page (--dl-key)

The download flow used by the shell layer (download.sh) is:

  1. ``get_apkmonk_resp()`` fetches the app index page.
  2. ``get_apkmonk_vers()`` calls ``--versions`` to list available versions.
  3. ``dl_apkmonk()`` calls ``--version-url`` to get the version page URL,
     fetches that page via ``req``, then calls ``--dl-key`` to extract the
     ``pkg`` and ``key`` query parameters embedded in a ``<script>`` tag.
  4. The shell computes the API URL and fetches the JSON download link.

Inspired by nikhilbadyal/docker-py-revanced src/downloader/apkmonk.py.

Usage:
    # List available versions
    curl -s https://www.apkmonk.com/app/com.google.android.youtube/ \\
        | python3 apkmonk_search.py --versions

    # Get version-specific page URL
    curl -s https://www.apkmonk.com/app/com.google.android.youtube/ \\
        | python3 apkmonk_search.py --version-url --version 19.16.39

    # Extract download key from a version page
    curl -s https://www.apkmonk.com/app/com.google.android.youtube/VERCODE/ \\
        | python3 apkmonk_search.py --dl-key
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from enum import Enum, auto

from selectolax.parser import HTMLParser

APKMONK_BASE_URL: str = "https://www.apkmonk.com"

# Pattern for pkg/key embedded in APKMonk's inline JavaScript.
# Matches: pkg=com.example&key=ABCDEF123
_DL_KEY_PATTERN: re.Pattern[str] = re.compile(r"pkg=([^&'\"]+)&key=([^'\"&\s]+)")


class Command(Enum):
    """Available parser modes."""

    VERSIONS = auto()
    VERSION_URL = auto()
    DL_KEY = auto()


@dataclass(frozen=True, slots=True)
class ParseResult:
    """Result of a parse operation.

    Attributes:
        success: Whether parsing succeeded.
        data: The parsed string or list of strings.
        error: Human-readable error message on failure.

    """

    success: bool
    data: str | list[str] | None
    error: str | None = None

    @classmethod
    def ok(cls, data: str | list[str]) -> ParseResult:
        """Create a successful result.

        Args:
            data: The parsed value.

        Returns:
            ParseResult with success=True.

        """
        return cls(success=True, data=data, error=None)

    @classmethod
    def err(cls, error: str) -> ParseResult:
        """Create a failed result.

        Args:
            error: Description of the failure.

        Returns:
            ParseResult with success=False.

        """
        return cls(success=False, data=None, error=error)


def parse_versions(html: str) -> ParseResult:
    """Extract version strings from an APKMonk app index page.

    The version table uses ``class="striped"`` rows.  Each row contains
    at least one ``<a>`` whose text is the human-readable version string.

    Args:
        html: Full HTML of the APKMonk app page.

    Returns:
        ParseResult with a list of version strings, or an error.

    """
    tree = HTMLParser(html)
    versions: list[str] = []
    seen: set[str] = set()

    for table in tree.css(".striped"):
        for link in table.css("a"):
            text = link.text(strip=True)
            if text and text not in seen:
                seen.add(text)
                versions.append(text)

    if versions:
        return ParseResult.ok(versions)
    return ParseResult.err("no versions found in APKMonk page")


def parse_version_url(html: str, version: str) -> ParseResult:
    """Find the version-specific download page URL on an APKMonk app page.

    Searches the striped version table for a row whose link text matches
    ``version`` and returns its ``href``.

    Args:
        html: Full HTML of the APKMonk app page.
        version: Exact version string to look for (e.g. ``"19.16.39"``).

    Returns:
        ParseResult with the absolute URL, or an error.

    """
    tree = HTMLParser(html)

    for table in tree.css(".striped"):
        for link in table.css("a"):
            if link.text(strip=True) == version:
                href = link.attributes.get("href", "")
                if href:
                    url = href if href.startswith("http") else APKMONK_BASE_URL + href
                    return ParseResult.ok(url)

    return ParseResult.err(f"version {version!r} not found on APKMonk page")


def parse_dl_key(html: str) -> ParseResult:
    """Extract the ``pkg`` and ``key`` values from an APKMonk version page.

    APKMonk embeds these in an inline ``<script>`` block as query parameters.
    The output format is ``pkg:key`` so the shell layer can split on ``:``.

    Args:
        html: Full HTML of an APKMonk version-specific page.

    Returns:
        ParseResult with ``"pkg:key"`` string, or an error.

    """
    tree = HTMLParser(html)

    for script in tree.css("script[type='text/javascript'], script:not([type])"):
        text = script.text(strip=False)
        if not text:
            continue
        match = _DL_KEY_PATTERN.search(text)
        if match:
            pkg_val = match.group(1)
            key_val = match.group(2)
            return ParseResult.ok(f"{pkg_val}:{key_val}")

    return ParseResult.err("pkg/key pair not found in APKMonk version page scripts")


def main(argv: list[str] | None = None) -> int:
    """CLI entry point.

    Args:
        argv: Command-line arguments (defaults to sys.argv).

    Returns:
        Exit code: 0 on success, 1 on parse failure, 2 on missing input.

    """
    parser = argparse.ArgumentParser(
        description="Parse APKMonk pages for version info and download keys",
    )

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--versions",
        action="store_true",
        help="List available version strings (one per line)",
    )
    group.add_argument(
        "--version-url",
        action="store_true",
        help="Output the URL of the version-specific page",
    )
    group.add_argument(
        "--dl-key",
        action="store_true",
        help="Extract pkg:key pair from a version page",
    )

    parser.add_argument(
        "--version",
        help="Version string (required with --version-url)",
    )

    args = parser.parse_args(argv)

    if args.version_url and not args.version:
        print("Error: --version is required with --version-url", file=sys.stderr)
        return 1

    try:
        html = sys.stdin.read()
    except KeyboardInterrupt:
        return 130

    if not html:
        print("Error: no HTML received on stdin", file=sys.stderr)
        return 2

    if args.versions:
        result = parse_versions(html)
        if result.success and isinstance(result.data, list):
            print("\n".join(result.data))
            return 0
        print(result.error, file=sys.stderr)
        return 1

    if args.version_url:
        result = parse_version_url(html, args.version)
        if result.success and isinstance(result.data, str):
            print(result.data)
            return 0
        print(result.error, file=sys.stderr)
        return 1

    # --dl-key
    result = parse_dl_key(html)
    if result.success and isinstance(result.data, str):
        print(result.data)
        return 0
    print(result.error, file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
