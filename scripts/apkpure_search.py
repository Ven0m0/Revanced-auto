#!/usr/bin/env python3
"""APKPure version and download link parser.

Scrapes APKPure.net for app versions and download URLs.
Inspired by X-Abhishek-X/ReVanced-Automated-Build-Scripts downloader_src/apkpure.py.

Usage:
    # Get latest version
    python3 apkpure_search.py --latest --name youtube --package com.google.android.youtube

    # Get download link for specific version
    python3 apkpure_search.py --download --name youtube --package com.google.android.youtube \
        --version 19.16.39

    # Get available versions
    python3 apkpure_search.py --versions --name youtube --package com.google.android.youtube
"""

import argparse
import sys

from selectolax.parser import HTMLParser

APKPURE_BASE = "https://apkpure.net"


def parse_latest_version(html_content: str) -> str | None:
    """Extract latest version from APKPure versions page.

    Args:
        html_content: HTML of the APKPure versions page.

    Returns:
        Latest version string, or None if not found.
    """
    tree = HTMLParser(html_content)
    ver_top = tree.css_first("div.ver-top-down")
    if ver_top is not None:
        dt_version = ver_top.attrs.get("data-dt-version")
        if dt_version:
            return dt_version.strip()

    ver_item = tree.css_first("div.ver-item a span.ver-item-n")
    if ver_item is not None:
        text = ver_item.text(strip=True)
        if text:
            return text

    return None


def parse_versions(html_content: str) -> list[str]:
    """Extract available versions from APKPure versions page.

    Args:
        html_content: HTML of the APKPure versions page.

    Returns:
        List of version strings.
    """
    tree = HTMLParser(html_content)
    versions: list[str] = []

    for item in tree.css("div.ver-item a span.ver-item-n"):
        text = item.text(strip=True)
        if text and text not in versions:
            versions.append(text)

    return versions


def parse_download_link(html_content: str) -> str | None:
    """Extract download URL from APKPure download page.

    Args:
        html_content: HTML of the APKPure download page.

    Returns:
        Download URL, or None if not found.
    """
    tree = HTMLParser(html_content)
    link = tree.css_first("a#download_link")
    if link is not None:
        href = link.attrs.get("href")
        if href:
            return href.strip()

    link = tree.css_first("a.da")
    if link is not None:
        href = link.attrs.get("href")
        if href:
            return href.strip()

    return None


def build_versions_url(name: str, package: str) -> str:
    """Build APKPure versions page URL.

    Args:
        name: App name slug on APKPure.
        package: Android package name.

    Returns:
        Full URL to versions page.
    """
    return f"{APKPURE_BASE}/{name}/{package}/versions"


def build_download_url(name: str, package: str, version: str) -> str:
    """Build APKPure download page URL.

    Args:
        name: App name slug on APKPure.
        package: Android package name.
        version: Version string.

    Returns:
        Full URL to download page.
    """
    return f"{APKPURE_BASE}/{name}/{package}/download/{version}"


def _handle_url_only(args: argparse.Namespace) -> None:
    if args.latest or args.versions:
        print(build_versions_url(args.name, args.package))
    elif args.download:
        print(build_download_url(args.name, args.package, args.version))
    sys.exit(0)


def _dispatch_command(args: argparse.Namespace, html_content: str) -> None:
    if args.latest:
        result = parse_latest_version(html_content)
        sys.exit(0 if result and print(result) is None else 1)

    if args.versions:
        versions = parse_versions(html_content)
        for v in versions:
            print(v)
        sys.exit(0 if versions else 1)

    if args.download:
        link = parse_download_link(html_content)
        sys.exit(0 if link and print(link) is None else 1)

    sys.exit(1)


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Parse APKPure pages for version info and download links",
    )
    parser.add_argument("--name", required=True, help="App name slug on APKPure")
    parser.add_argument("--package", required=True, help="Android package name")

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--latest", action="store_true", help="Get latest version")
    group.add_argument("--versions", action="store_true", help="List available versions")
    group.add_argument("--download", action="store_true", help="Get download link")

    parser.add_argument("--version", help="Version for download (required with --download)")
    parser.add_argument(
        "--url-only",
        action="store_true",
        help="Output only the constructed URL (no parsing)",
    )

    args = parser.parse_args()

    if args.download and not args.version:
        print("Error: --version is required with --download", file=sys.stderr)
        sys.exit(1)

    if args.url_only:
        _handle_url_only(args)

    try:
        html_content = sys.stdin.read()
    except KeyboardInterrupt:
        sys.exit(130)

    if not html_content:
        sys.exit(2)

    _dispatch_command(args, html_content)


if __name__ == "__main__":
    main()
