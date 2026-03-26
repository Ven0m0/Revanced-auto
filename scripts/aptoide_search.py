#!/usr/bin/env python3
"""Aptoide API client for APK version lookup and download.

Uses the Aptoide public REST API to find app versions and download URLs.
Inspired by X-Abhishek-X/ReVanced-Automated-Build-Scripts downloader_src/aptoide.py.

Usage:
    # Get latest version
    python3 aptoide_search.py --latest --package com.google.android.youtube

    # Get download link for specific version
    python3 aptoide_search.py --download --package com.google.android.youtube --version 19.16.39

    # Get available versions
    python3 aptoide_search.py --versions --package com.google.android.youtube

    # Architecture-specific query
    python3 aptoide_search.py --latest --package com.google.android.youtube --arch arm64-v8a
"""

from __future__ import annotations

import argparse
import base64
import sys
from dataclasses import dataclass
from enum import Enum, auto
from typing import TypedDict

import orjson

APTOIDE_API: str = "https://ws75.aptoide.com/api/7"


class AptoideFile(TypedDict, total=False):
    """Aptoide file information.

    Attributes:
        vername: Version name string.
        vercode: Version code integer.
        path: Download path/URL.

    """

    vername: str
    vercode: int
    path: str


class AptoideApp(TypedDict, total=False):
    """Aptoide app information.

    Attributes:
        file: File information dict.

    """

    file: AptoideFile


class AptoideDataList(TypedDict, total=False):
    """Aptoide datalist wrapper.

    Attributes:
        list: List of app information.

    """

    list: list[AptoideApp]


class AptoideResponse(TypedDict, total=False):
    """Aptoide API search/list response.

    Attributes:
        datalist: Datalist containing app information.

    """

    datalist: AptoideDataList


class AptoideMetaResponse(TypedDict, total=False):
    """Aptoide API meta response.

    Attributes:
        data: App information.

    """

    data: AptoideApp


# Type aliases
type ArchType = str
type QParam = str


class Arch(Enum):
    """Supported architectures."""

    UNIVERSAL = "universal"
    ALL = "all"
    ARM64_V8A = "arm64-v8a"
    ARMEABI_V7A = "armeabi-v7a"

    @property
    def cpu_string(self) -> str:
        """Return CPU architecture string for API query."""
        match self:
            case Arch.ARM64_V8A:
                return "arm64-v8a,armeabi-v7a,armeabi"
            case Arch.ARMEABI_V7A:
                return "armeabi-v7a,armeabi"
            case _:
                return ""


class Command(Enum):
    """Available CLI commands."""

    LATEST = auto()
    VERSIONS = auto()
    DOWNLOAD = auto()
    URL = auto()
    FIND_VERCODE = auto()
    PARSE_META = auto()


class CommandError(Exception):
    """Exception raised when an invalid command is specified."""

    def __init__(self, message: str = "no command specified") -> None:
        """Initialize the exception with a default message."""
        super().__init__(message)


@dataclass(frozen=True, slots=True)
class QueryBuilder:
    """Builder for Aptoide API URLs.

    Attributes:
        package: Android package name.
        arch: Target architecture.
        limit: Maximum number of results.

    """

    package: str
    arch: str = "universal"
    limit: int = 50

    def _build_q_param(self) -> QParam:
        """Build Aptoide architecture filter parameter.

        Returns:
            URL query parameter string for architecture filtering.

        """
        match Arch(self.arch):
            case Arch.UNIVERSAL | Arch.ALL:
                return ""
            case Arch.ARM64_V8A:
                cpu = "arm64-v8a,armeabi-v7a,armeabi"
                q_str = f"myCPU={cpu}&leanback=0"
                encoded = base64.b64encode(q_str.encode()).decode()
                return f"&q={encoded}"
            case Arch.ARMEABI_V7A:
                cpu = "armeabi-v7a,armeabi"
                q_str = f"myCPU={cpu}&leanback=0"
                encoded = base64.b64encode(q_str.encode()).decode()
                return f"&q={encoded}"
            case _:
                return ""

    def build_search_url(self) -> str:
        """Build Aptoide search API URL.

        Returns:
            Full API URL.

        """
        q = self._build_q_param()
        return f"{APTOIDE_API}/apps/search?query={self.package}&limit=1&trusted=true{q}"

    def build_versions_url(self) -> str:
        """Build Aptoide list versions API URL.

        Returns:
            Full API URL.

        """
        q = self._build_q_param()
        return f"{APTOIDE_API}/listAppVersions?package_name={self.package}&limit={self.limit}{q}"

    def build_meta_url(self, vercode: int) -> str:
        """Build Aptoide getAppMeta API URL.

        Args:
            vercode: Version code integer.

        Returns:
            Full API URL.

        """
        q = self._build_q_param()
        return f"{APTOIDE_API}/getAppMeta?package_name={self.package}&vercode={vercode}{q}"


@dataclass(frozen=True, slots=True)
class DownloadInfo:
    """Download information result.

    Attributes:
        url: Download URL.
        vercode: Version code if available.
        version: Version name if available.

    """

    url: str
    vercode: int | None = None
    version: str | None = None


def is_valid_aptoide_response(data: object) -> bool:
    """TypeGuard to validate Aptoide response structure.

    Args:
        data: Parsed JSON data.

    Returns:
        True if data is a valid AptoideResponse.

    """
    if not isinstance(data, dict):
        return False

    datalist = data.get("datalist")
    if not isinstance(datalist, dict):
        return False

    app_list = datalist.get("list")
    return isinstance(app_list, list)


def is_valid_meta_response(data: object) -> bool:
    """TypeGuard to validate Aptoide meta response structure.

    Args:
        data: Parsed JSON data.

    Returns:
        True if data is a valid AptoideMetaResponse.

    """
    if not isinstance(data, dict):
        return False

    app_data = data.get("data")
    return isinstance(app_data, dict)


def parse_search_version(json_content: str) -> str | None:
    """Extract latest version from Aptoide search response.

    Args:
        json_content: JSON response from apps/search API.

    Returns:
        Version name string, or None if not found.

    """
    try:
        data = orjson.loads(json_content)
    except orjson.JSONDecodeError:
        return None

    if not is_valid_aptoide_response(data):
        return None

    app_list = data["datalist"]["list"]
    if not app_list:
        return None

    file_info = app_list[0].get("file", {})
    vername = file_info.get("vername")
    return str(vername) if vername else None


def parse_search_download(json_content: str) -> str | None:
    """Extract download URL from Aptoide search response (latest version).

    Args:
        json_content: JSON response from apps/search API.

    Returns:
        Download URL, or None if not found.

    """
    try:
        data = orjson.loads(json_content)
    except orjson.JSONDecodeError:
        return None

    if not is_valid_aptoide_response(data):
        return None

    app_list = data["datalist"]["list"]
    if not app_list:
        return None

    file_info = app_list[0].get("file", {})
    path = file_info.get("path")
    return str(path) if path else None


def parse_versions_list(json_content: str) -> list[str]:
    """Extract available versions from Aptoide listAppVersions response.

    Args:
        json_content: JSON response from listAppVersions API.

    Returns:
        List of version name strings.

    """
    versions: list[str] = []

    try:
        data = orjson.loads(json_content)
    except orjson.JSONDecodeError:
        return versions

    if not is_valid_aptoide_response(data):
        return versions

    for app in data["datalist"]["list"]:
        file_info = app.get("file", {})
        vername = file_info.get("vername")
        if vername and vername not in versions:
            versions.append(str(vername))

    return versions


def find_vercode(json_content: str, version: str) -> int | None:
    """Find version code for a specific version name.

    Args:
        json_content: JSON response from listAppVersions API.
        version: Target version name.

    Returns:
        Version code integer, or None if not found.

    """
    try:
        data = orjson.loads(json_content)
    except orjson.JSONDecodeError:
        return None

    if not is_valid_aptoide_response(data):
        return None

    for app in data["datalist"]["list"]:
        file_info = app.get("file", {})
        if file_info.get("vername") == version:
            try:
                return int(file_info["vercode"])
            except (KeyError, ValueError):
                return None

    return None


def parse_meta_download(json_content: str) -> str | None:
    """Extract download URL from Aptoide getAppMeta response.

    Args:
        json_content: JSON response from getAppMeta API.

    Returns:
        Download URL, or None if not found.

    """
    try:
        data = orjson.loads(json_content)
    except orjson.JSONDecodeError:
        return None

    if not is_valid_meta_response(data):
        return None

    file_info = data["data"].get("file", {})
    path = file_info.get("path")
    return str(path) if path else None


@dataclass(frozen=True, slots=True)
class AppConfig:
    """Application configuration.

    Attributes:
        package: Android package name.
        arch: Target architecture.
        version: Optional version string.

    """

    package: str
    arch: str = "universal"
    version: str | None = None


def determine_command(args: argparse.Namespace) -> Command:
    """Determine command from CLI arguments.

    Args:
        args: Parsed CLI arguments.

    Returns:
        Command to execute.

    """
    if args.latest:
        return Command.LATEST
    if args.versions:
        return Command.VERSIONS
    if args.download:
        return Command.DOWNLOAD
    if args.url:
        return Command.URL
    if args.find_vercode:
        return Command.FIND_VERCODE
    if args.parse_meta:
        return Command.PARSE_META

    raise CommandError


def execute_url_command(config: AppConfig) -> int:
    """Execute URL generation command.

    Args:
        config: App configuration.

    Returns:
        Exit code.

    """
    builder = QueryBuilder(config.package, config.arch)

    if config.version:
        print(builder.build_versions_url())
    else:
        print(builder.build_search_url())

    return 0


def execute_latest_command(json_content: str) -> int:
    """Execute latest version command.

    Args:
        json_content: JSON response from API.

    Returns:
        Exit code.

    """
    result = parse_search_version(json_content)
    if result:
        print(result)
        return 0
    return 1


def execute_versions_command(json_content: str) -> int:
    """Execute versions list command.

    Args:
        json_content: JSON response from API.

    Returns:
        Exit code.

    """
    versions = parse_versions_list(json_content)
    for v in versions:
        print(v)
    return 0 if versions else 1


def execute_download_command(json_content: str, config: AppConfig) -> int:
    """Execute download URL command.

    Args:
        json_content: JSON response from API.
        config: App configuration with optional version.

    Returns:
        Exit code.

    """
    version = (config.version or "").lower()

    match version:
        case "latest" | "":
            result = parse_search_download(json_content)
        case _:
            result = parse_meta_download(json_content)

    if result:
        print(result)
        return 0
    return 1


def execute_find_vercode_command(json_content: str, config: AppConfig) -> int:
    """Execute find version code command.

    Args:
        json_content: JSON response from API.
        config: App configuration with required version.

    Returns:
        Exit code.

    """
    if not config.version:
        return 1

    vercode = find_vercode(json_content, config.version)
    if vercode is not None:
        print(vercode)
        return 0
    return 1


def execute_parse_meta_command(json_content: str) -> int:
    """Execute parse meta response command.

    Args:
        json_content: JSON response from API.

    Returns:
        Exit code.

    """
    result = parse_meta_download(json_content)
    if result:
        print(result)
        return 0
    return 1


def main() -> int:
    """CLI entry point.

    Returns:
        Exit code: 0 on success, 1 on failure, 130 on interrupt.

    """
    parser = argparse.ArgumentParser(
        description="Query Aptoide API for app versions and download links",
    )
    parser.add_argument("--package", required=True, help="Android package name")
    parser.add_argument(
        "--arch",
        default="universal",
        help="Device architecture (default: universal)",
    )

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--latest", action="store_true", help="Get latest version")
    group.add_argument("--versions", action="store_true", help="List available versions")
    group.add_argument("--download", action="store_true", help="Get download link")
    group.add_argument("--url", action="store_true", help="Output API URL only")
    group.add_argument("--find-vercode", action="store_true", help="Find vercode for version")
    group.add_argument("--parse-meta", action="store_true", help="Parse getAppMeta response")

    parser.add_argument("--version", help="Version for download/find-vercode")

    args = parser.parse_args()

    config = AppConfig(
        package=args.package,
        arch=args.arch,
        version=args.version,
    )

    command = determine_command(args)

    if command == Command.URL:
        return execute_url_command(config)

    if (args.download or args.find_vercode) and not config.version:
        print("Error: --version is required with --download/--find-vercode", file=sys.stderr)
        return 1

    try:
        json_content = sys.stdin.read()
    except KeyboardInterrupt:
        return 130

    if not json_content:
        return 2

    match command:
        case Command.LATEST:
            return execute_latest_command(json_content)
        case Command.VERSIONS:
            return execute_versions_command(json_content)
        case Command.DOWNLOAD:
            return execute_download_command(json_content, config)
        case Command.FIND_VERCODE:
            return execute_find_vercode_command(json_content, config)
        case Command.PARSE_META:
            return execute_parse_meta_command(json_content)
        case _:
            return 1


if __name__ == "__main__":
    sys.exit(main())
