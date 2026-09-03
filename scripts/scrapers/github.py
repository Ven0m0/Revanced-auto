"""GitHub Releases download source.

Ported from nvbangg/builder-for-morphe's src/scrapers/github.py, itself part
of krvstek/uni-apks (GPLv3, header below kept per license terms). Changes
from upstream: adapted to this repo's ScraperBase/VersionInfo/DownloadResult
contracts instead of upstream's NetworkManager/BaseScraper/AppMetadata,
uses scripts.utils.network.gh_req/gh_dl instead of a private
NetworkManager._gh_headers, lists the whole ``/releases`` history rather
than a single tag (matching _resolve_github_release_asset's reasoning in
scripts/builder/app_processor.py -- ``/releases/latest`` hides prereleases),
and reuses APKMirror's APKEditor-based bundle merger instead of a second one.
"""
# ---------------------------------------------------------
# Copyright (C) 2026 krvstek
#
# DO NOT REMOVE OR ALTER THIS COPYRIGHT HEADER.
# This file is part of uni-apks.
# Canonical source: https://github.com/krvstek/uni-apks
#
# Licensed under the GNU GPLv3. You may modify this file,
# but you MUST keep this original copyright notice intact
# and prominently state any changes made.
# See the AUTHORS file in the root directory for details.
# ---------------------------------------------------------

from __future__ import annotations

import asyncio
import json
import re
import tempfile
from pathlib import Path
from typing import Any

from scripts.scrapers.apkmirror import is_apk_bundle, merge_apkm_splits
from scripts.scrapers.base import DownloadResult, DownloadSource, ScraperBase, VersionInfo
from scripts.utils.network import gh_dl, gh_req

_ARCH_SUFFIX = re.compile(r"(?:-(all|arm64-v8a|armeabi-v7a|x86_64|x86))?(?:\.apk\.apkm|\.apk|\.apkm)$", re.IGNORECASE)
_UNIVERSAL_ARCHS = frozenset({"universal", "all", "both"})


def _select_asset(assets: list[dict[str, Any]], arch: str) -> dict[str, Any] | None:
    apk_assets = [a for a in assets if str(a.get("name", "")).endswith((".apk", ".apkm"))]
    for asset in apk_assets:
        name = str(asset.get("name", ""))
        match = _ARCH_SUFFIX.search(name)
        file_arch = match.group(1).lower() if match and match.group(1) else "all"
        if arch in _UNIVERSAL_ARCHS:
            if file_arch not in ("all", "universal"):
                continue
        elif file_arch not in (arch, "all"):
            continue
        return asset
    return None


def _find_release(releases: list[dict[str, Any]], version: str | None) -> dict[str, Any] | None:
    if version is None:
        return releases[0] if releases else None
    version_f = version.strip().lstrip("v")
    for release in releases:
        tag = str(release.get("tag_name") or release.get("name") or "").strip().lstrip("v")
        if tag == version_f:
            return release
    return None


class GitHubScraper(ScraperBase):
    """Scraper for GitHub Releases. ``pkg_name`` is ``owner/repo``."""

    def __init__(self) -> None:
        super().__init__(DownloadSource.GITHUB)

    async def _list_releases(self, pkg_name: str) -> list[dict[str, Any]]:
        url = f"https://api.github.com/repos/{pkg_name.strip('/')}/releases"
        raw = await asyncio.to_thread(gh_req, url)
        releases = json.loads(raw)
        return releases if isinstance(releases, list) else []

    async def get_versions(self, pkg_name: str, **kwargs: object) -> list[VersionInfo]:
        releases = await self._list_releases(pkg_name)
        versions: list[VersionInfo] = []
        for release in releases:
            tag = release.get("tag_name") or release.get("name")
            if not tag:
                continue
            if any(str(a.get("name", "")).endswith((".apk", ".apkm")) for a in release.get("assets", [])):
                versions.append(VersionInfo(version=str(tag)))
        return versions

    async def download(
        self,
        pkg_name: str,
        version: str | None,
        output_path: Path,
        **kwargs: object,
    ) -> DownloadResult:
        arch = str(kwargs.get("arch", "universal"))
        releases = await self._list_releases(pkg_name)
        release = _find_release(releases, version)
        if release is None:
            return DownloadResult(success=False, error=f"No release found for {pkg_name!r} version {version!r}")

        asset = _select_asset(release.get("assets", []), arch)
        if asset is None:
            return DownloadResult(success=False, error=f"No matching APK/APKM asset for arch {arch!r}")

        asset_name = str(asset["name"])
        bundle = asset_name.endswith(".apkm")
        dest = output_path.with_suffix(".apkm") if bundle else output_path
        ok = await asyncio.to_thread(gh_dl, dest, str(asset["url"]))
        if not ok:
            return DownloadResult(success=False, error=f"Download failed: {asset_name}")

        if bundle and is_apk_bundle(dest):
            merged = output_path.with_suffix(".apk")
            with tempfile.TemporaryDirectory(prefix="github_scraper_") as tmp:
                merge_ok = await asyncio.to_thread(merge_apkm_splits, Path(tmp), dest, merged)
            if not merge_ok:
                return DownloadResult(success=False, error="Failed to merge APK bundle splits")
            dest = merged

        resolved_version = str(release.get("tag_name") or release.get("name") or version)
        return DownloadResult(success=True, file_path=dest, version=resolved_version)
