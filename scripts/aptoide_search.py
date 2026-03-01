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

import argparse
import base64
import json
import sys

APTOIDE_API = "https://ws75.aptoide.com/api/7"


def build_q_param(arch: str) -> str:
    """Build Aptoide architecture filter parameter.

    Args:
        arch: Device architecture (arm64-v8a, armeabi-v7a, or universal).

    Returns:
        URL query parameter string for architecture filtering.
    """
    if arch in ("universal", "all"):
        return ""

    cpu_map: dict[str, str] = {
        "arm64-v8a": "arm64-v8a,armeabi-v7a,armeabi",
        "armeabi-v7a": "armeabi-v7a,armeabi",
    }

    cpu = cpu_map.get(arch, "")
    if cpu:
        q_str = f"myCPU={cpu}&leanback=0"
        encoded = base64.b64encode(q_str.encode()).decode()
        return f"&q={encoded}"
    return ""


def build_search_url(package: str, arch: str = "universal") -> str:
    """Build Aptoide search API URL.

    Args:
        package: Android package name.
        arch: Device architecture.

    Returns:
        Full API URL.
    """
    q = build_q_param(arch)
    return f"{APTOIDE_API}/apps/search?query={package}&limit=1&trusted=true{q}"


def build_versions_url(package: str, arch: str = "universal", limit: int = 50) -> str:
    """Build Aptoide list versions API URL.

    Args:
        package: Android package name.
        arch: Device architecture.
        limit: Max number of versions to return.

    Returns:
        Full API URL.
    """
    q = build_q_param(arch)
    return f"{APTOIDE_API}/listAppVersions?package_name={package}&limit={limit}{q}"


def build_meta_url(package: str, vercode: int, arch: str = "universal") -> str:
    """Build Aptoide getAppMeta API URL.

    Args:
        package: Android package name.
        vercode: Version code integer.
        arch: Device architecture.

    Returns:
        Full API URL.
    """
    q = build_q_param(arch)
    return f"{APTOIDE_API}/getAppMeta?package_name={package}&vercode={vercode}{q}"


def parse_search_version(json_content: str) -> str | None:
    """Extract latest version from Aptoide search response.

    Args:
        json_content: JSON response from apps/search API.

    Returns:
        Version name string, or None if not found.
    """
    try:
        data = json.loads(json_content)
        app_list = data.get("datalist", {}).get("list", [])
        if app_list:
            return str(app_list[0].get("file", {}).get("vername", ""))
    except (json.JSONDecodeError, KeyError, IndexError):
        pass
    return None


def parse_search_download(json_content: str) -> str | None:
    """Extract download URL from Aptoide search response (latest version).

    Args:
        json_content: JSON response from apps/search API.

    Returns:
        Download URL, or None if not found.
    """
    try:
        data = json.loads(json_content)
        app_list = data.get("datalist", {}).get("list", [])
        if app_list:
            return str(app_list[0].get("file", {}).get("path", ""))
    except (json.JSONDecodeError, KeyError, IndexError):
        pass
    return None


def parse_versions_list(json_content: str) -> list[str]:
    """Extract available versions from Aptoide listAppVersions response.

    Args:
        json_content: JSON response from listAppVersions API.

    Returns:
        List of version name strings.
    """
    versions: list[str] = []
    try:
        data = json.loads(json_content)
        for app in data.get("datalist", {}).get("list", []):
            vername = app.get("file", {}).get("vername")
            if vername and vername not in versions:
                versions.append(str(vername))
    except (json.JSONDecodeError, KeyError):
        pass
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
        data = json.loads(json_content)
        for app in data.get("datalist", {}).get("list", []):
            if app.get("file", {}).get("vername") == version:
                return int(app["file"]["vercode"])
    except (json.JSONDecodeError, KeyError, ValueError):
        pass
    return None


def parse_meta_download(json_content: str) -> str | None:
    """Extract download URL from Aptoide getAppMeta response.

    Args:
        json_content: JSON response from getAppMeta API.

    Returns:
        Download URL, or None if not found.
    """
    try:
        data = json.loads(json_content)
        return str(data.get("data", {}).get("file", {}).get("path", ""))
    except (json.JSONDecodeError, KeyError):
        pass
    return None


def _handle_url_mode(args: argparse.Namespace) -> None:
    if args.version:
        print(build_versions_url(args.package, args.arch))
    else:
        print(build_search_url(args.package, args.arch))
    sys.exit(0)


def _dispatch_command(args: argparse.Namespace, json_content: str) -> None:
    if args.latest:
        result = parse_search_version(json_content)
        sys.exit(0 if result and print(result) is None else 1)

    if args.versions:
        versions = parse_versions_list(json_content)
        for v in versions:
            print(v)
        sys.exit(0 if versions else 1)

    if args.download:
        result = (
            parse_search_download(json_content)
            if args.version.lower() == "latest"
            else parse_meta_download(json_content)
        )
        sys.exit(0 if result and print(result) is None else 1)

    if args.find_vercode:
        vercode = find_vercode(json_content, args.version)
        sys.exit(0 if vercode is not None and print(vercode) is None else 1)

    if args.parse_meta:
        result = parse_meta_download(json_content)
        sys.exit(0 if result and print(result) is None else 1)

    sys.exit(1)


def main() -> None:
    """CLI entry point."""
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

    if args.url:
        _handle_url_mode(args)

    if (args.download or args.find_vercode) and not args.version:
        print("Error: --version is required with --download/--find-vercode", file=sys.stderr)
        sys.exit(1)

    try:
        json_content = sys.stdin.read()
    except KeyboardInterrupt:
        sys.exit(130)

    if not json_content:
        sys.exit(2)

    _dispatch_command(args, json_content)


if __name__ == "__main__":
    main()
