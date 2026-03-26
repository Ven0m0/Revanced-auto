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

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from enum import Enum, auto

from selectolax.parser import HTMLParser

APKPURE_BASE: str = "https://apkpure.net"

# Type aliases
type VersionList = list[str]
type CommandResult = str | VersionList | None


class Command(Enum):
    """Available CLI commands."""

    LATEST = auto()
    VERSIONS = auto()
    DOWNLOAD = auto()
    URL_ONLY = auto()


class CommandError(Exception):
    """Exception raised when an invalid command is specified."""

    def __init__(self, message: str = "no command specified") -> None:
        """Initialize the exception with a default message."""
        super().__init__(message)


@dataclass(frozen=True, slots=True)
class URLBuilder:
    """Builder for APKPure URLs.

    Attributes:
        name: App name slug on APKPure.
        package: Android package name.

    """

    name: str
    package: str

    @property
    def base_path(self) -> str:
        """Return the base URL path for this app."""
        return f"{APKPURE_BASE}/{self.name}/{self.package}"

    def build_versions_url(self) -> str:
        """Build APKPure versions page URL.

        Returns:
            Full URL to versions page.

        """
        return f"{self.base_path}/versions"

    def build_download_url(self, version: str) -> str:
        """Build APKPure download page URL.

        Args:
            version: Version string.

        Returns:
            Full URL to download page.

        """
        return f"{self.base_path}/download/{version}"


@dataclass(frozen=True, slots=True)
class ParseResult:
    """Result of a parsing operation.

    Attributes:
        success: Whether parsing was successful.
        data: The parsed data if successful.
        error: Error message if unsuccessful.

    """

    success: bool
    data: str | list[str] | None
    error: str | None = None

    @classmethod
    def ok(cls, data: str | list[str]) -> ParseResult:
        """Create a successful parse result."""
        return cls(success=True, data=data, error=None)

    @classmethod
    def err(cls, error: str) -> ParseResult:
        """Create a failed parse result."""
        return cls(success=False, data=None, error=error)


@dataclass(frozen=True, slots=True)
class AppConfig:
    """Configuration for APKPure operations.

    Attributes:
        name: App name slug.
        package: Android package name.
        version: Optional version string for download.

    """

    name: str
    package: str
    version: str | None = None


def parse_latest_version(html_content: str) -> ParseResult:
    """Extract latest version from APKPure versions page.

    Args:
        html_content: HTML of the APKPure versions page.

    Returns:
        ParseResult with version string or error.

    """
    tree = HTMLParser(html_content)

    # Try primary selector
    ver_top = tree.css_first("div.ver-top-down")
    if ver_top is not None:
        dt_version = ver_top.attrs.get("data-dt-version")
        if dt_version and (version := dt_version.strip()):
            return ParseResult.ok(version)

    # Fallback selector
    ver_item = tree.css_first("div.ver-item a span.ver-item-n")
    if ver_item is not None:
        text = ver_item.text(strip=True)
        if text:
            return ParseResult.ok(text)

    return ParseResult.err("latest version not found")


def parse_versions(html_content: str) -> ParseResult:
    """Extract available versions from APKPure versions page.

    Args:
        html_content: HTML of the APKPure versions page.

    Returns:
        ParseResult with list of version strings.

    """
    tree = HTMLParser(html_content)
    versions: VersionList = []

    for item in tree.css("div.ver-item a span.ver-item-n"):
        text = item.text(strip=True)
        if text and text not in versions:
            versions.append(text)

    if versions:
        return ParseResult.ok(versions)

    return ParseResult.err("no versions found")


def parse_download_link(html_content: str) -> ParseResult:
    """Extract download URL from APKPure download page.

    Args:
        html_content: HTML of the APKPure download page.

    Returns:
        ParseResult with download URL.

    """
    tree = HTMLParser(html_content)

    # Try primary selector
    link = tree.css_first("a#download_link")
    if link is not None:
        href = link.attrs.get("href")
        if href and (url := href.strip()):
            return ParseResult.ok(url)

    # Fallback selector
    link = tree.css_first("a.da")
    if link is not None:
        href = link.attrs.get("href")
        if href and (url := href.strip()):
            return ParseResult.ok(url)

    return ParseResult.err("download link not found")


def determine_command(args: argparse.Namespace) -> Command:
    """Determine which command to execute based on CLI arguments.

    Args:
        args: Parsed CLI arguments.

    Returns:
        The command to execute.

    """
    if args.url_only:
        return Command.URL_ONLY
    if args.latest:
        return Command.LATEST
    if args.versions:
        return Command.VERSIONS
    if args.download:
        return Command.DOWNLOAD

    # Should never reach here due to required mutually exclusive group
    raise CommandError


def execute_command(
    command: Command,
    config: AppConfig,
    html_content: str,
    args: argparse.Namespace,
) -> tuple[CommandResult, int]:
    """Execute the determined command.

    Args:
        command: Command to execute.
        config: App configuration.
        html_content: HTML content from stdin.
        args: Parsed CLI arguments.

    Returns:
        Tuple of (result data, exit code).

    """
    builder = URLBuilder(config.name, config.package)

    match command:
        case Command.URL_ONLY:
            if args.latest or args.versions:
                return (builder.build_versions_url(), 0)
            if args.download:
                if not config.version:
                    return (None, 1)
                return (builder.build_download_url(config.version), 0)
            return (None, 1)

        case Command.LATEST:
            result = parse_latest_version(html_content)
            if result.success and isinstance(result.data, str):
                return (result.data, 0)
            return (None, 1)

        case Command.VERSIONS:
            result = parse_versions(html_content)
            if result.success and isinstance(result.data, list):
                for v in result.data:
                    print(v)
                return (result.data, 0 if result.data else 1)
            return (None, 1)

        case Command.DOWNLOAD:
            result = parse_download_link(html_content)
            if result.success and isinstance(result.data, str):
                return (result.data, 0)
            return (None, 1)

        case _:
            return (None, 1)


def main() -> int:
    """CLI entry point.

    Returns:
        Exit code: 0 on success, 1 on failure, 130 on interrupt.

    """
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
        return 1

    config = AppConfig(name=args.name, package=args.package, version=args.version)

    command = determine_command(args)

    # URL-only mode doesn't need HTML input
    if command == Command.URL_ONLY:
        result, code = execute_command(command, config, "", args)
        if result and isinstance(result, str):
            print(result)
        return code

    # All other modes need HTML content
    try:
        html_content = sys.stdin.read()
    except KeyboardInterrupt:
        return 130

    if not html_content:
        return 2

    result, code = execute_command(command, config, html_content, args)

    # Single value output (not list)
    if result and not isinstance(result, list):
        print(result)

    return code


if __name__ == "__main__":
    sys.exit(main())
