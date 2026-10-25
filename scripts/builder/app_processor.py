#!/usr/bin/env python3
"""Application processing module for APK patching workflow.

Orchestrates the complete build process for ReVanced/RVX apps,
replacing the legacy scripts/lib/app_processor.sh implementation.
"""

from __future__ import annotations

import functools
import json
import logging
import os
import re
import shutil
import sys
import tempfile
import threading
import urllib.parse
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from types import TracebackType
from typing import TYPE_CHECKING, Any, Protocol, Self

import httpx

from scripts.builder.cli_profiles import (
    BUILTIN_PROFILES,
    CLIProfile,
    CLIProfileType,
    PatchCommandConfig,
    detect_cli_profile,
)
from scripts.lib.plugins import dispatch_plugins
from scripts.scrapers.base import DownloadSource
from scripts.search.version_resolver import parse_patch_names, parse_versions
from scripts.utils.apk import load_signatures
from scripts.utils.java import JavaRunner

if TYPE_CHECKING:
    from collections.abc import Callable

    from scripts.builder.config import AppConfig, Config
    from scripts.utils.keystore import SigningKeystore

logger = logging.getLogger(__name__)

# Message prefix of the ValueError DownloadManager.resolve raises when ``compatible`` filters out everything.
_NO_COMPATIBLE = "no patch-compatible version"
# Permanent client errors (not 429) from ScraperBase._request_with_retry: the source is unusable, not merely flaky.
_PERMANENT_4XX = re.compile(r"HTTP 4(?!29)\d\d for ")


def _blocks_fallback(error: Exception) -> bool:
    """True if a source failure may hide a compatible version (outage), so newest-version fallback is unsafe.

    "No compatible version" and "no versions at all" are definitive answers; permanent 4xx (e.g. a Cloudflare 403)
    means the source cannot be consulted at all. Anything else (5xx, 429, network errors) is transient.
    """
    if not isinstance(error, (ValueError, RuntimeError)):
        return True
    text = str(error)
    if isinstance(error, ValueError):
        return not (_NO_COMPATIBLE in text or text.startswith("No versions found"))
    return _PERMANENT_4XX.search(text) is None


class NoCompatibleVersionError(RuntimeError):
    """Every candidate source was reachable but listed none of the patch-compatible versions."""


class Architecture(Enum):
    """Supported CPU architectures."""

    ARM64_V8A = "arm64-v8a"
    ARM_V7A = "arm-v7a"
    BOTH = "both"
    ALL = "all"

    @classmethod
    def from_string(cls, value: str) -> Architecture:
        """Parse architecture from string.

        Args:
            value: Architecture string (arm64-v8a, arm-v7a, both, all).

        Returns:
            Architecture enum value.

        Raises:
            ValueError: If value is not a valid architecture.
        """
        # build.yml offers the real ABI name armeabi-v7a; the enum uses arm-v7a.
        value_lower = {"armeabi-v7a": "arm-v7a"}.get(value.lower(), value.lower())
        for arch in cls:
            if arch.value == value_lower:
                return arch
        raise ValueError(f"Invalid architecture: {value}")


# Re-exported for backwards compatibility: this used to be a locally defined
# duplicate Enum with the same members, which broke identity/equality checks
# against scrapers (DownloadManager._get_scraper() matches on this exact
# Enum class). Use the scrapers' canonical DownloadSource everywhere.


@dataclass
class BuildResult:
    """Result of a single app build operation.

    Attributes:
        app_name: Name of the app that was built.
        brand: ReVanced brand variant (e.g., "revanced", "rvx").
        version: Version string of the built APK.
        arch: Architecture that was built (arm64-v8a, arm-v7a, or "universal").
        output_path: Path to the generated APK file.
        success: Whether the build succeeded.
        error: Error message if build failed.
        changelog: List of patches applied in this build.
        build_time: Time taken to build in seconds.
    """

    app_name: str
    brand: str
    version: str
    arch: str
    output_path: Path
    success: bool
    error: str | None = None
    changelog: list[str] = field(default_factory=list)
    build_time: float | None = None


@dataclass
class BuildSummary:
    """Summary of all build operations.

    Attributes:
        total: Total number of build operations.
        succeeded: List of successful build results.
        failed: List of failed build results.
        start_time: When the build process started.
        end_time: When the build process finished.
    """

    total: int
    succeeded: list[BuildResult]
    failed: list[BuildResult]
    start_time: datetime = field(default_factory=lambda: datetime.now(UTC))
    end_time: datetime | None = None

    @property
    def success_count(self) -> int:
        """Number of successful builds."""
        return len(self.succeeded)

    @property
    def failure_count(self) -> int:
        """Number of failed builds."""
        return len(self.failed)

    @property
    def duration(self) -> float | None:
        """Build duration in seconds, if finished."""
        if self.end_time:
            return (self.end_time - self.start_time).total_seconds()
        return None


class VersionResolver(Protocol):
    """Protocol for version resolution implementations."""

    def resolve(
        self,
        app_id: str,
        source: DownloadSource,
        *,
        compatible: list[str] | None = None,
        include_beta: bool = False,
        timeout: int = 300,
    ) -> tuple[str, str]:
        """Resolve the newest app version on a download source.

        Args:
            app_id: Application package ID.
            source: Download source to use.
            compatible: Patch-compatible versions to restrict to; empty or None means no filter.
            include_beta: Also consider alpha/beta releases.
            timeout: Request timeout in seconds.

        Returns:
            Tuple of (version_string, version_code).

        Raises:
            ValueError: No version (or no compatible version) exists on this source.
        """
        ...


class DownloadManager(Protocol):
    """Protocol for APK download implementations."""

    def download(
        self,
        app_id: str,
        version: str,
        output_path: Path,
        source: DownloadSource,
        *,
        arch: str | None = None,
        dpi: str | None = None,
        timeout: int = 300,
        expected_cert: str | None = None,
    ) -> Path:
        """Download stock APK from source.

        Args:
            app_id: Application package ID.
            version: Version to download.
            output_path: Where to save the APK.
            source: Download source.
            arch: Target architecture.
            dpi: Target DPI.
            timeout: Request timeout in seconds.
            expected_cert: Expected stock signing certificate SHA-256.

        Returns:
            Path to downloaded APK.
        """
        ...


def _is_morphe_patches_source(source: str) -> bool:
    """Detect Morphe-style patch sources, which publish ``.mpp`` bundles instead of ``.rvp``.

    Mirrors the source-pattern match in scripts/lib/prebuilts.sh's
    resolve_rv_artifact (``MorpheApp/* | */morphe-* | */rvx-morphed |
    */anddea-rvx-morphed | */patcheddit``).
    """
    lower = source.strip().lower()
    return (
        lower.startswith("morpheapp/")
        or "/morphe-" in lower
        or lower.endswith(("/rvx-morphed", "/anddea-rvx-morphed", "/patcheddit"))
    )


@functools.cache
def _resolve_github_release_asset(
    source: str,
    ext: str,
    fallback_ext: str | None = None,
    version: str = "latest",
) -> tuple[str, str, str]:
    """Find the GitHub release asset of ``source`` with a ``.ext`` (or ``.fallback_ext``) file.

    ``latest`` walks ``/releases`` newest-first, skipping drafts and prereleases; ``dev`` also
    accepts prereleases. Any other value is a pinned tag, fetched from ``/releases/tags/{version}``
    with a ``v{version}`` retry on 404. Asset filenames aren't matched by prefix (they vary per fork,
    e.g. MorpheApp's CLI asset is ``morphe-desktop-*-all.jar``); only the extension matters.
    Cached so every arch variant of a run resolves to the same tag with one API call.

    Returns:
        Tuple of (asset_filename, asset_api_url, tag). The API asset URL (not
        browser_download_url) requires an octet-stream Accept header to
        stream binary content, which gh_dl() already sets.
    """
    from scripts.utils.network import gh_req

    api = f"https://api.github.com/repos/{source}/releases"
    releases: list[dict[str, Any]]
    if version in ("latest", "dev"):
        releases = [
            r for r in json.loads(gh_req(api)) if not r.get("draft") and (version == "dev" or not r.get("prerelease"))
        ]
    else:
        try:
            raw = gh_req(f"{api}/tags/{version}")
        except httpx.HTTPStatusError as e:
            if e.response.status_code != httpx.codes.NOT_FOUND:
                raise
            raw = gh_req(f"{api}/tags/v{version}")
        releases = [json.loads(raw)]

    wanted = (ext, fallback_ext) if fallback_ext else (ext,)
    for release in releases:
        for candidate_ext in wanted:
            for asset in release.get("assets", []):
                name = asset.get("name", "")
                if name.endswith(f".{candidate_ext}"):
                    return name, asset["url"], release.get("tag_name", version)

    exts = " or ".join(f".{e}" for e in wanted)
    msg = f"No {exts} asset found in {source} releases ({version})"
    raise RuntimeError(msg)


def _derive_scraper_pkg_name(download_url: str, source: DownloadSource) -> str:
    """Derive the package identifier a scraper expects from a configured ``*-dlurl`` listing-page URL.

    Each download source encodes the package differently in its URL:
    APKMirror, GitHub, and APKPure all use a two-segment path (e.g.
    ``https://apkmirror.com/apk/google-inc/youtube-music`` ->
    ``google-inc/youtube-music``; ``https://github.com/owner/repo`` ->
    ``owner/repo``; ``https://apkpure.net/sd-maid-2-se/eu.darken.sdmse`` ->
    ``sd-maid-2-se/eu.darken.sdmse`` -- APKPureScraper needs both the name
    slug and the package id, not just the id, or it builds a URL with the
    package id duplicated in the slug's place); Uptodown puts its app slug in
    the *subdomain*, not the path (``https://tiktok.en.uptodown.com/android``
    -> ``tiktok`` -- UptodownScraper._build_app_url formats it right back into
    ``https://{app}.en.uptodown.com/android``, so reading the path's last
    segment ("android") would break every lookup); most other sources put the
    real Android package id as the final path segment (e.g.
    ``.../apks/com.google.android.apps.youtube.music``).
    """
    if source == DownloadSource.UPTODOWN:
        netloc = urllib.parse.urlparse(download_url).netloc
        return netloc.split(".", 1)[0]
    path = urllib.parse.urlparse(download_url).path.strip("/")
    if not path:
        return download_url
    if source == DownloadSource.APKMIRROR:
        return path.removeprefix("apk/")
    if source in (DownloadSource.GITHUB, DownloadSource.APKPURE):
        return path
    return path.rsplit("/", 1)[-1]


_KNOWN_NATIVE_ARCHS = ("arm64-v8a", "armeabi-v7a")


def _normalize_native_arch(arch: str) -> str:
    """Map ``Architecture`` enum values to real Android native-lib ABI folder names."""
    return "armeabi-v7a" if arch == "arm-v7a" else arch


def _riplib_values(target_arch: str, *, keep_semantics: bool) -> list[str]:
    """Native-lib architecture values for the patcher's rip/strip-libs flag.

    Two incompatible conventions exist: Morphe's ``--striplibs`` lists archs
    to *keep* (one value); classic ReVanced CLI's ``--rip-lib``/``-r`` lists
    archs to *strip*, repeated per value. ``keep_semantics`` selects which.
    """
    normalized = _normalize_native_arch(target_arch)
    if keep_semantics:
        return [normalized]
    return [arch for arch in _KNOWN_NATIVE_ARCHS if arch != normalized]


class JobRunner:
    """Manages parallel job execution with concurrency limiting.

    Attributes:
        max_workers: Maximum number of concurrent jobs.
    """

    def __init__(self, max_workers: int = 2) -> None:
        """Initialize JobRunner.

        Args:
            max_workers: Maximum number of concurrent jobs.
        """
        self.max_workers = max_workers
        self._executor = ThreadPoolExecutor(max_workers=max_workers)
        self._futures: list[Future[Any]] = []

    def submit(self, func: Callable[..., Any], *args: Any, **kwargs: Any) -> Future[Any]:
        """Submit a job for execution.

        Args:
            func: Function to execute.
            *args: Positional arguments for the function.
            **kwargs: Keyword arguments for the function.

        Returns:
            Future representing the pending job.
        """
        future = self._executor.submit(func, *args, **kwargs)
        self._futures.append(future)
        return future

    def wait_all(self) -> list[tuple[Future[Any], Any]]:
        """Wait for all submitted jobs to complete.

        Returns:
            List of (future, result) tuples.
        """
        results = []
        for future in self._futures:
            try:
                result = future.result()
                results.append((future, result))
            except Exception as e:
                results.append((future, e))
        return results

    def shutdown(self, wait: bool = True) -> None:
        """Shutdown the executor.

        Args:
            wait: Whether to wait for pending jobs.
        """
        self._executor.shutdown(wait=wait)

    def __enter__(self) -> Self:
        """Enter context manager."""
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """Exit context manager."""
        self.shutdown(wait=True)


@dataclass
class AppBuildContext:
    """Context for building a single app architecture variant.

    Attributes:
        app_name: Name of the app.
        app_id: Package ID.
        brand: ReVanced brand.
        version: App version.
        arch: Target architecture.
        output_path: Output APK path.
        source: Download source (the candidate that resolved a version).
        download_url: Pre-configured download URL.
        scraper_pkg_name: Package identifier as expected by the download source's
            scraper (e.g. the APKMirror URL slug), derived from download_url.
        candidates: Configured (source, dlurl) pairs in failover order, used to
            retry the stock APK download on a different source if the first fails.
        patches_source: Patches source repository(s).
        patches_version: Patches version.
        cli_source: CLI source repository.
        cli_version: CLI version.
        cli_jar: Path to CLI JAR (downloaded).
        patches_jars: Paths to patches JARs (downloaded).
        excluded_patches: Patches to exclude.
        included_patches: Patches to include.
        exclusive_patches: Whether to use exclusive patch loading.
        integrations: Path to integrations JAR.
        riplib: Whether to use riplib.
        merge_patches: Patches to merge.
        options: Additional patcher options.
        patch_options: Per-patch option values (name -> {key: value}).
        bundle_patch_names: Patch names listed by each bundle, parallel to patches_jars.
    """

    app_name: str
    app_id: str
    brand: str
    version: str
    arch: str
    output_path: Path
    source: DownloadSource
    download_url: str = ""
    scraper_pkg_name: str = ""
    patches_source: str | list[str] = "MorpheApp/morphe-patches"
    patches_version: str = "latest"
    cli_source: str = "MorpheApp/morphe-cli"
    cli_version: str = "latest"
    cli_jar: Path | None = None
    patches_jars: list[Path] = field(default_factory=list)
    excluded_patches: list[str] = field(default_factory=list)
    included_patches: list[str] = field(default_factory=list)
    exclusive_patches: bool = False
    integrations: Path | None = None
    riplib: bool = True
    merge_patches: list[Path] = field(default_factory=list)
    options: dict[str, Any] = field(default_factory=dict)
    patch_options: dict[str, dict[str, Any]] = field(default_factory=dict)
    candidates: list[tuple[DownloadSource, str]] = field(default_factory=list)
    bundle_patch_names: list[list[str]] = field(default_factory=list)


class AppProcessor:
    """Orchestrates the complete build workflow for an app.

    Manages configuration parsing, prebuilt downloads, APK patching,
    and output generation with parallel job execution support.

    Attributes:
        config: Global configuration object.
        java_runner: Java subprocess runner.
        version_resolver: Optional version resolver.
        download_manager: Optional download manager.
    """

    def __init__(
        self,
        config: Config,
        java_runner: JavaRunner,
        version_resolver: VersionResolver | None = None,
        download_manager: DownloadManager | None = None,
    ) -> None:
        """Initialize AppProcessor.

        Args:
            config: Global configuration object.
            java_runner: Java subprocess runner.
            version_resolver: Optional version resolver.
            download_manager: Optional download manager.
        """
        self.config = config
        self.java_runner = java_runner
        self.version_resolver = version_resolver
        self.download_manager = download_manager
        # Serializes prebuilt fetches so parallel variants never unlink a jar another is using.
        self._prebuilt_lock = threading.Lock()
        self._refreshed_prebuilts: set[Path] = set()

    @property
    def parallel_jobs(self) -> int:
        """Get configured parallel job count."""
        return self.config.global_settings.parallel_jobs or 2

    def process_all(self) -> BuildSummary:
        """Process all enabled apps from config.

        Returns:
            BuildSummary with results for all builds.
        """
        start_time = datetime.now(UTC)
        all_results: list[BuildResult] = []

        logger.info("Processing all enabled apps")

        enabled_apps = [app for app in self.config.apps.values() if app.enabled]

        if not enabled_apps:
            logger.info("No enabled apps to process")
            return BuildSummary(
                total=0,
                succeeded=[],
                failed=[],
                start_time=start_time,
                end_time=datetime.now(UTC),
            )

        # Convert the keystore once up front so parallel builds never race on it.
        try:
            _ = self._signing
        except Exception as e:
            logger.error("Keystore preparation failed: %s", e)
            failed = [
                BuildResult(
                    app_name=app.options.get("app_name", app.name),
                    brand=app.options.get("rv_brand", "revanced"),
                    version="unknown",
                    arch="unknown",
                    output_path=Path(),
                    success=False,
                    error=f"Keystore preparation failed: {e}",
                )
                for app in enabled_apps
            ]
            return BuildSummary(
                total=len(failed), succeeded=[], failed=failed, start_time=start_time, end_time=datetime.now(UTC)
            )

        with JobRunner(max_workers=self.parallel_jobs) as runner:
            futures: dict[Future[BuildResult], str] = {}

            for app_config in enabled_apps:
                try:
                    arch = self._parse_architecture(app_config)
                except ValueError as e:
                    logger.error("Skipping %s: %s", app_config.name, e)
                    all_results.append(
                        BuildResult(
                            app_name=app_config.options.get("app_name", app_config.name),
                            brand=app_config.options.get("rv_brand", "revanced"),
                            version="unknown",
                            arch="unknown",
                            output_path=Path(),
                            success=False,
                            error=str(e),
                        )
                    )
                    continue
                arch_list = self._get_architecture_list(arch)

                for arch_variant in arch_list:
                    future = runner.submit(
                        self._build_app_variant,
                        app_config,
                        arch_variant,
                    )
                    futures[future] = app_config.name

            for future, app_name in futures.items():
                try:
                    result = future.result()
                    all_results.append(result)
                except Exception as e:
                    logger.error("Build failed with exception: %s", e)
                    all_results.append(
                        BuildResult(
                            app_name=app_name,
                            brand="unknown",
                            version="unknown",
                            arch="unknown",
                            output_path=Path(),
                            success=False,
                            error=str(e),
                        )
                    )

        summary = BuildSummary(
            total=len(all_results),
            succeeded=[r for r in all_results if r.success],
            failed=[r for r in all_results if not r.success],
            start_time=start_time,
            end_time=datetime.now(UTC),
        )

        return summary

    def _build_app_variant(
        self,
        app_config: AppConfig,
        arch: str,
    ) -> BuildResult:
        """Build a single app variant for specific architecture.

        Args:
            app_config: App configuration.
            arch: Target architecture.

        Returns:
            BuildResult for this variant.
        """
        import time

        start_time = time.time()

        app_name = app_config.options.get("app_name", app_config.name)
        brand = app_config.options.get("rv_brand", "revanced")

        logger.info(
            "Building %s (%s) for architecture %s",
            app_name,
            brand,
            arch,
        )

        try:
            context = self._prepare_build_context(app_config, arch)
        except Exception as e:
            logger.error("Failed to prepare build context: %s", e)
            return BuildResult(
                app_name=app_name,
                brand=brand,
                version="unknown",
                arch=arch,
                output_path=Path(),
                success=False,
                error=f"Failed to prepare build context: {e}",
                build_time=time.time() - start_time,
            )

        try:
            result = self._execute_build(context)
            return result
        except Exception as e:
            logger.error("Build failed: %s", e)
            return BuildResult(
                app_name=app_name,
                brand=brand,
                version=context.version,
                arch=arch,
                output_path=Path(),
                success=False,
                error=str(e),
                build_time=time.time() - start_time,
            )

    def _prepare_build_context(
        self,
        app_config: AppConfig,
        arch: str,
    ) -> AppBuildContext:
        """Prepare build context for app variant.

        Args:
            app_config: App configuration.
            arch: Target architecture.

        Returns:
            Prepared AppBuildContext.
        """
        app_name = app_config.options.get("app_name", app_config.name)
        brand = app_config.options.get("rv_brand", "revanced")
        candidates = self._candidate_download_sources(app_config)

        version = app_config.version or "auto"

        source, download_url = candidates[0]
        scraper_pkg_name = _derive_scraper_pkg_name(download_url, source) if download_url else app_config.name

        patches_source = app_config.patches_source or self.config.global_settings.patches_source
        patches_version = self.config.global_settings.patches_version

        cli_source = app_config.cli_source or self.config.global_settings.cli_source
        cli_version = self.config.global_settings.cli_version

        output_dir = Path("build")
        output_dir.mkdir(exist_ok=True)

        output_name = f"{app_name}-{version}-{arch}"
        output_path = output_dir / f"{output_name}.apk"

        return AppBuildContext(
            app_name=app_name,
            app_id=app_config.name,
            brand=brand,
            version=version,
            arch=arch,
            output_path=output_path,
            source=source,
            download_url=download_url,
            scraper_pkg_name=scraper_pkg_name,
            patches_source=patches_source,
            patches_version=patches_version,
            cli_source=cli_source,
            cli_version=cli_version,
            excluded_patches=app_config.exclude_patches,
            included_patches=app_config.patches,
            exclusive_patches=app_config.exclusive,
            riplib=self.config.global_settings.riplib,
            options=app_config.options,
            patch_options=app_config.patch_options,
            candidates=candidates,
        )

    def _resolve_version_with_failover(
        self,
        candidates: list[tuple[DownloadSource, str]],
        *,
        compatible: list[str],
        include_beta: bool,
    ) -> tuple[str, list[tuple[DownloadSource, str]]]:
        """Resolve a version by trying each candidate source in order.

        Returns the resolved version and ``candidates`` reordered so the
        source that resolved comes first, followed by the rest in their
        original order -- so a later download failure can still fail over.
        """
        if self.version_resolver is None:
            msg = "No version resolver configured"
            raise RuntimeError(msg)

        errors: list[str] = []
        saw_incompatible = False
        blocked = False
        for i, (source, download_url) in enumerate(candidates):
            pkg_name = _derive_scraper_pkg_name(download_url, source) if download_url else ""
            try:
                version, _ = self.version_resolver.resolve(
                    pkg_name, source, compatible=compatible, include_beta=include_beta
                )
            except Exception as e:
                errors.append(f"{source.value}: {e}")
                saw_incompatible = saw_incompatible or (isinstance(e, ValueError) and _NO_COMPATIBLE in str(e))
                blocked = blocked or _blocks_fallback(e)
                continue
            return version, [candidates[i], *candidates[:i], *candidates[i + 1 :]]

        msg = f"Failed to resolve version from any configured source: {'; '.join(errors)}"
        if compatible and saw_incompatible and not blocked:
            raise NoCompatibleVersionError(msg)
        raise RuntimeError(msg)

    def _execute_build(self, context: AppBuildContext) -> BuildResult:
        """Execute the actual build process.

        Args:
            context: Build context.

        Returns:
            BuildResult of the build.
        """
        dispatch_plugins(context, "pre_pipeline")

        cli_jar, patches_jars = self._ensure_prebuilts(context)
        context.cli_jar = cli_jar
        context.patches_jars = patches_jars
        self._resolve_version(context)
        stock_apk = self._download_stock_apk(context)
        # Resolved once: with cli_profile = "auto" each resolution starts a JVM.
        cli_profile = self._resolve_cli_profile(context)
        context.bundle_patch_names = self._bundle_patch_names(context, cli_profile)
        changelog = self._get_changelog(context)
        patched_apk = self._run_patcher(context, stock_apk, cli_profile)

        dispatch_plugins(context, "post_pipeline")

        return BuildResult(
            app_name=context.app_name,
            brand=context.brand,
            version=context.version,
            arch=context.arch,
            output_path=patched_apk,
            success=True,
            changelog=changelog,
        )

    def _download_stock_apk(self, context: AppBuildContext) -> Path:
        """Download stock APK, failing over across the configured candidates.

        Args:
            context: Build context.

        Returns:
            Path to downloaded APK.
        """
        if not self.download_manager:
            msg = "No download manager configured"
            raise RuntimeError(msg)

        candidates = context.candidates or [(context.source, context.download_url)]
        # Arch in the name keeps parallel arch variants from overwriting each other's stock APK.
        output_path = Path(tempfile.gettempdir()) / f"stock-{context.app_name}-{context.version}-{context.arch}.apk"
        errors: list[str] = []
        package = self._patches_package(context)
        expected_cert = load_signatures().get(package) if package else None
        if not expected_cert:
            logger.info("No stock signature entry in assets/sig.txt for %s; skipping stock APK check", context.app_name)
        for source, download_url in candidates:
            pkg_name = _derive_scraper_pkg_name(download_url, source) if download_url else context.app_id
            try:
                return self.download_manager.download(
                    pkg_name,
                    context.version,
                    output_path,
                    source,
                    arch=context.arch,
                    expected_cert=expected_cert,
                )
            except Exception as e:
                logger.warning("Download from %s failed for %s: %s", source.value, context.app_name, e)
                errors.append(f"{source.value}: {e}")
        msg = f"Failed to download stock APK for {context.app_name} from any source: {'; '.join(errors)}"
        raise RuntimeError(msg)

    def _fetch_prebuilt(self, target: Path, url: str) -> None:
        """Download ``url`` to ``target`` unless a cached copy may be reused."""
        from scripts.utils.network import gh_dl

        with self._prebuilt_lock:
            # gh_dl returns True for any existing file, so a refresh must unlink first (once per run).
            if not self.config.global_settings.use_cache and target not in self._refreshed_prebuilts:
                target.unlink(missing_ok=True)
                self._refreshed_prebuilts.add(target)
            if not gh_dl(target, url):
                msg = f"Failed to download {url}"
                raise RuntimeError(msg)

    def _ensure_prebuilts(
        self,
        context: AppBuildContext,
    ) -> tuple[Path, list[Path]]:
        """Ensure CLI and patches JARs are downloaded.

        Cache files are keyed by repo and release tag, so a file is reused only when both match.

        Args:
            context: Build context.

        Returns:
            Tuple of (cli_jar_path, patches_jars_paths).
        """
        cache_dir = Path(os.environ.get("CACHE_DIR", ".cache"))
        prebuilts_dir = cache_dir / "prebuilts"
        prebuilts_dir.mkdir(parents=True, exist_ok=True)

        cli_name, cli_url, cli_tag = _resolve_github_release_asset(
            context.cli_source, "jar", version=context.cli_version
        )
        cli_jar = prebuilts_dir / f"{context.cli_source.replace('/', '-')}-{cli_tag}{Path(cli_name).suffix}"
        self._fetch_prebuilt(cli_jar, cli_url)

        patches_sources = (
            [context.patches_source] if isinstance(context.patches_source, str) else context.patches_source
        )

        from scripts.scrapers.external_bundles import (
            is_external_bundles_source,
            parse_bundle_selector,
            resolve_bundle,
        )

        patches_jars: list[Path] = []
        for patches_src in patches_sources:
            is_morphe = _is_morphe_patches_source(patches_src)
            ext = "mpp" if is_morphe else "rvp"

            if is_external_bundles_source(patches_src):
                selector = parse_bundle_selector(patches_src) or context.app_id
                entry = resolve_bundle(selector, context.patches_version)
                patches_url = entry.download_url
                suffix = Path(urllib.parse.urlparse(patches_url).path).suffix or f".{ext}"
                name = f"external-{selector}-{entry.version}{suffix}".replace("/", "-")
            else:
                fallback_ext = "rvp" if is_morphe else "mpp"
                asset_name, patches_url, tag = _resolve_github_release_asset(
                    patches_src, ext, fallback_ext, version=context.patches_version
                )
                name = f"{patches_src.replace('/', '-')}-{tag}{Path(asset_name).suffix}"

            patches_jar = prebuilts_dir / name
            self._fetch_prebuilt(patches_jar, patches_url)
            patches_jars.append(patches_jar)

        return cli_jar, patches_jars

    def _patches_package(self, context: AppBuildContext) -> str:
        """Android package id for list-versions: the ``package-name`` option, else derived from a dlurl."""
        explicit = str(context.options.get("package_name", "")).strip()
        if explicit:
            return explicit
        # Only these sources put the real package id as the URL's last path segment.
        pkg_sources = (DownloadSource.APKPURE, DownloadSource.ARCHIVE, DownloadSource.APTOIDE, DownloadSource.APKMonk)
        for source, url in context.candidates:
            if source in pkg_sources and url:
                return _derive_scraper_pkg_name(url, source).rsplit("/", 1)[-1]
        return ""

    def _compatible_versions(self, context: AppBuildContext) -> list[str]:
        """App versions the configured patch bundles support, per Morphe's ``list-versions``."""
        pkg = self._patches_package(context)
        if not pkg:
            logger.warning("No package id for %s (set package-name); using the newest store version", context.app_name)
            return []
        if not context.cli_jar:
            return []

        patches_args = [arg for jar in context.patches_jars for arg in ("--patches", str(jar))]
        result = self.java_runner.run_jar(
            str(context.cli_jar),
            ["list-versions", *patches_args, "-f", pkg],
            timeout=120,
        )
        if result.returncode != 0:
            msg = f"list-versions failed for {pkg}: {result.stderr.strip()}"
            raise RuntimeError(msg)
        return parse_versions(result.stdout)

    def _resolve_version(self, context: AppBuildContext) -> None:
        """Turn ``auto``/``latest``/``beta`` into a concrete store version; pinned versions pass through."""
        mode = context.version.strip().lower()
        if mode not in ("auto", "latest", "beta"):
            return

        compatible: list[str] = []
        if mode == "auto":
            compatible = self._compatible_versions(context)
            if not compatible:
                logger.warning("No patch-compatible versions known for %s; using latest", context.app_name)

        sources = context.candidates or [(context.source, context.download_url)]
        try:
            version, candidates = self._resolve_version_with_failover(
                sources, compatible=compatible, include_beta=mode == "beta"
            )
        except NoCompatibleVersionError as e:
            # APKMirror lists only ~10 recent versions, so the compatible ones may be unlisted everywhere.
            logger.warning("%s for %s; falling back to the newest store version", e, context.app_name)
            version, candidates = self._resolve_version_with_failover(sources, compatible=[], include_beta=False)
        context.version = version
        context.candidates = candidates
        context.source, context.download_url = candidates[0]
        if context.download_url:
            context.scraper_pkg_name = _derive_scraper_pkg_name(context.download_url, context.source)
        context.output_path = Path("build") / f"{context.app_name}-{version}-{context.arch}.apk"

    def _bundle_patch_names(self, context: AppBuildContext, profile: CLIProfile) -> list[list[str]]:
        """List each bundle's patch names, so selections can follow the bundle that owns them."""
        if not context.cli_jar:
            return [[] for _ in context.patches_jars]

        lists: list[list[str]] = []
        failures: list[str] = []
        for jar in context.patches_jars:
            stdout = ""
            try:
                result = self.java_runner.run_jar(
                    str(context.cli_jar),
                    [*profile.build_list_patches_args([jar]), "-u"],
                    timeout=120,
                )
                stdout = result.stdout
                error = "" if result.returncode == 0 else (result.stderr.strip() or f"exit {result.returncode}")
            except Exception as e:
                error = str(e) or type(e).__name__
            if error:
                logger.warning("Failed to list patches in %s: %s", jar.name, error)
                failures.append(f"{jar.name}: {error}")
                lists.append([])
                continue
            lists.append(parse_patch_names(stdout))

        # Without every bundle's list, selections would silently land on the last bundle.
        if failures and len(context.patches_jars) > 1:
            msg = f"Cannot map patches to bundles: {'; '.join(failures)}"
            raise RuntimeError(msg)

        known = {name for names in lists for name in names}
        for name in context.included_patches:
            if known and name not in known:
                logger.warning("Patch %r for %s is not in any patch bundle", name, context.app_name)
        return lists

    def _get_changelog(self, context: AppBuildContext) -> list[str]:
        """Get list of patches that will be applied.

        Args:
            context: Build context with ``bundle_patch_names`` filled in.

        Returns:
            List of patch names.
        """
        available = list(dict.fromkeys(name for names in context.bundle_patch_names for name in names))
        if context.exclusive_patches:
            found = set(available)
            return [name for name in context.included_patches if name in found]
        excluded = set(context.excluded_patches)
        return [name for name in available if name not in excluded]

    def _run_patcher(
        self,
        context: AppBuildContext,
        stock_apk: Path,
        cli_profile: CLIProfile,
    ) -> Path:
        """Run the patcher CLI, then re-sign the output with apksigner (v1+v2 only).

        Args:
            context: Build context.
            stock_apk: Path to stock APK.
            cli_profile: Resolved patcher CLI profile.

        Returns:
            Path to patched APK.
        """
        riplib_libs: list[str] = []
        if context.riplib and self._profile_supports_riplib(cli_profile):
            keep_semantics = cli_profile.profile_type in (CLIProfileType.MORPHE_CLI, CLIProfileType.ADOBO_CLI)
            riplib_libs = _riplib_values(context.arch, keep_semantics=keep_semantics)

        # Morphe and apksigner write into a private temp dir; build/ (uploaded by CI even on failure)
        # only ever receives the final, successfully re-signed APK.
        work_dir = Path(tempfile.mkdtemp(prefix=f"patch-{context.app_name}-{context.arch}-"))
        try:
            final = self._patch_and_sign(context, stock_apk, cli_profile, riplib_libs, work_dir)
            context.output_path.parent.mkdir(parents=True, exist_ok=True)
            context.output_path.unlink(missing_ok=True)
            shutil.move(final, context.output_path)
        finally:
            shutil.rmtree(work_dir, ignore_errors=True)
        return context.output_path

    def _patch_and_sign(
        self,
        context: AppBuildContext,
        stock_apk: Path,
        cli_profile: CLIProfile,
        riplib_libs: list[str],
        work_dir: Path,
    ) -> Path:
        """Patch into ``work_dir`` and re-sign there; return the finished APK inside ``work_dir``."""
        signing = self._signing
        unsigned = work_dir / f"{context.output_path.stem}.apk"
        # Later bundles win on duplicate names, matching docs/CONFIG.md.
        patch_bundle = {name: idx for idx, names in enumerate(context.bundle_patch_names) for name in names}
        patch_config = PatchCommandConfig(
            apk_path=stock_apk,
            output_path=unsigned,
            patches_jars=context.patches_jars,
            exclude=context.excluded_patches,
            include=context.included_patches,
            merge=context.merge_patches,
            keystore=signing.patcher_keystore,
            keystore_alias=signing.alias,
            keystore_password=signing.password,
            keystore_entry_password=signing.entry_password,
            signer=signing.alias,
            rip_lib=riplib_libs,
            exclusive=context.exclusive_patches,
            options=context.patch_options,
            patch_bundle=patch_bundle,
        )
        patch_args = cli_profile.build_patch_args(patch_config)

        result = self.java_runner.run_jar(
            str(context.cli_jar),
            patch_args,
            timeout=600,
        )

        if result.returncode != 0:
            raise RuntimeError(f"Patching failed: {result.stderr}")

        if signing.apksigner_keystore is None:
            return unsigned

        from scripts.utils.apk import sign_apk

        signed = work_dir / f"{context.output_path.stem}.signed.apk"
        # apksigner reads the original (or PKCS12) keystore; the BKS copy exists only for Morphe.
        if not sign_apk(
            unsigned, signed, signing.apksigner_keystore, signing.password, signing.alias, signing.entry_password
        ):
            msg = f"Re-signing {context.output_path.name} with apksigner failed"
            raise RuntimeError(msg)
        return signed

    def _resolve_cli_profile(self, context: AppBuildContext) -> CLIProfile:
        """Resolve the CLI profile for a build context.

        Honors the global ``cli_profile`` setting (default ``"auto"``) by
        inspecting the CLI JAR when needed. Falls back to ``MORPHE_CLI`` when
        detection fails or no JAR is available, which is consistent with the
        default ``cli_source`` in the repository's ``config.toml``.

        Args:
            context: Build context with a downloaded ``cli_jar``.

        Returns:
            The resolved :class:`CLIProfile` to use for building args.
        """
        requested = getattr(self.config.global_settings, "cli_profile", "auto")
        normalized = (requested or "auto").strip().lower()

        if normalized != "auto":
            for profile_type, profile in BUILTIN_PROFILES.items():
                if profile_type.value == normalized or profile_type.name.lower() == normalized:
                    return profile
            logger.warning("Unknown cli_profile %r; falling back to auto-detect", requested)

        if context.cli_jar and context.cli_jar.exists():
            try:
                return detect_cli_profile(context.cli_jar)
            except Exception as e:
                logger.debug("CLI profile detection failed (%s); using MORPHE_CLI", e)

        return BUILTIN_PROFILES[CLIProfileType.MORPHE_CLI]

    @staticmethod
    def _profile_supports_riplib(profile: CLIProfile) -> bool:
        """Return True when the profile declares a RIP_LIB arg mapping."""
        return "RIP_LIB" in profile.patch_args and profile.patch_args["RIP_LIB"] is not None

    def _source_keystore_path(self) -> Path | None:
        """The configured keystore (``keystore_path`` or ``assets/ks.keystore``), or None if there is none."""
        if self.config.global_settings.keystore_path:
            return Path(self.config.global_settings.keystore_path)
        default_keystore = Path("assets/ks.keystore")
        return default_keystore if default_keystore.exists() else None

    @functools.cached_property
    def _signing(self) -> SigningKeystore:
        """Signing credentials and keystore copies, converted once.

        Morphe's patcher only accepts BKS keystores and converts anything
        else via a BouncyCastle copy whose jar signature it rejects (the
        "JCE cannot authenticate the provider BC" failure) -- converting
        once here up front avoids ever handing it a non-BKS keystore.
        process_all reads this before starting parallel builds.
        """
        from scripts.utils.keystore import prepare_signing

        source = self._source_keystore_path()
        if source is None:
            logger.warning("No keystore configured; outputs keep the patcher's own signature (no apksigner pass)")
        return prepare_signing(source, self.config.global_settings.keystore_alias)

    def _parse_architecture(self, app_config: AppConfig) -> Architecture:
        """Parse architecture from app config, falling back to the global ``arch``.

        Args:
            app_config: App configuration.

        Returns:
            Architecture enum value.
        """
        arch_str = app_config.options.get("arch") or self.config.global_settings.arch
        return Architecture.from_string(arch_str)

    def _get_architecture_list(self, arch: Architecture) -> list[str]:
        """Get list of architectures to build.

        Args:
            arch: Architecture enum value.

        Returns:
            List of architecture strings.
        """
        if arch == Architecture.BOTH or arch == Architecture.ALL:
            return [Architecture.ARM64_V8A.value, Architecture.ARM_V7A.value]
        return [arch.value]

    # APKMirror first: most complete/official listings, and its scraper's
    # selectors are kept current against the live site (see
    # _list_release_pages()/_get_download_url() in apkmirror.py). The rest
    # follow in reliability order; Uptodown last -- smallest, slowest-to-page
    # catalog of the lot.
    _SOURCE_PREFERENCE: tuple[DownloadSource, ...] = (
        DownloadSource.APKMIRROR,
        DownloadSource.ARCHIVE,
        DownloadSource.APKPURE,
        DownloadSource.GITHUB,
        DownloadSource.APTOIDE,
        DownloadSource.APKMonk,
        DownloadSource.UPTODOWN,
    )

    def _candidate_download_sources(self, app_config: AppConfig) -> list[tuple[DownloadSource, str]]:
        """List every download source the app has a configured ``*-dlurl`` for, in preference order."""
        candidates: list[tuple[DownloadSource, str]] = []
        for source in self._SOURCE_PREFERENCE:
            url = self._get_download_url(app_config, source)
            if url:
                candidates.append((source, url))
        if not candidates:
            # No *-dlurl configured at all: fall back to APKMirror keyed by
            # the app's own config name, matching the old single-source
            # default.
            candidates.append((DownloadSource.APKMIRROR, ""))
        return candidates

    def _get_download_url(self, app_config: AppConfig, source: DownloadSource) -> str:
        """Get the configured ``*-dlurl`` option value for ``source``."""
        options = app_config.options

        url_map: dict[DownloadSource, str] = {
            DownloadSource.APKMIRROR: str(options.get("apkmirror_dlurl", "")),
            DownloadSource.UPTODOWN: str(options.get("uptodown_dlurl", "")),
            DownloadSource.APKPURE: str(options.get("apkpure_dlurl", "")),
            DownloadSource.ARCHIVE: str(options.get("archive_dlurl", "")),
            DownloadSource.APTOIDE: str(options.get("aptoide_dlurl", "")),
            DownloadSource.APKMonk: str(options.get("apkmonk_dlurl", "")),
            DownloadSource.GITHUB: str(options.get("github_dlurl", "")),
        }

        return url_map.get(source, "")


def _write_build_log(summary: BuildSummary, path: Path | None = None) -> None:
    """Write a build.md summary of this build for the GitHub release notes.

    The Python builder never wrote this file, unlike build.sh (the legacy
    bash path), so the release job's "Combine build logs" step always had
    nothing to combine -- confirmed in CI (no build-log-* artifacts were
    ever produced, well before that step even runs).
    """
    path = path or Path("build.md")
    lines: list[str] = []
    for result in summary.succeeded:
        lines.append(f"### {result.app_name} ({result.brand}) {result.version} - {result.arch}")
        lines.extend(f"- {patch}" for patch in result.changelog)
        lines.append("")

    lines.extend(
        [
            "### MicroG / GmsCore (Required for YouTube & YT Music)",
            "Download and install one of the following GmsCore providers:",
            "- [ReVanced GmsCore](https://github.com/ReVanced/GmsCore/releases/latest)",
            "- [Wst_Xda GmsCore (Morphe)](https://github.com/MorpheApp/MicroG-RE/releases/latest)",
            "- [YT-Advanced GmsCore (Rex)](https://github.com/YT-Advanced/GmsCore/releases/latest)",
            "",
        ]
    )

    if summary.failed:
        lines.append("Skipped:")
        lines.extend(f"- {result.app_name}: {result.error}" for result in summary.failed)

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run(config: Config) -> int:
    """Build every enabled app in ``config``, print a summary, and write build.md.

    Args:
        config: Loaded configuration, including any CLI overrides.

    Returns:
        Exit code (0 when every build succeeded, 1 otherwise).
    """
    from scripts.scrapers.download_manager import DownloadManager

    # DownloadManager also implements the VersionResolver protocol
    # (.resolve()) via the same underlying scrapers, so one instance
    # covers both roles.
    download_manager = DownloadManager()
    processor = AppProcessor(
        config,
        JavaRunner(),
        version_resolver=download_manager,
        download_manager=download_manager,
    )

    summary = processor.process_all()

    print(f"Built {summary.success_count}/{summary.total} apps")
    if summary.failed:
        print("Failed apps:")
        for result in summary.failed:
            print(f"  - {result.app_name}: {result.error}")

    _write_build_log(summary)

    return 0 if summary.failure_count == 0 else 1


def main(argv: list[str]) -> int:
    """Main entry point for app processor CLI.

    Args:
        argv: Command line arguments.

    Returns:
        Exit code (0 for success, 1 for error).
    """
    if len(argv) < 2:
        print("Usage: app_processor.py <config.toml> [config2.toml ...]", file=sys.stderr)
        return 1

    try:
        from scripts.builder.config import load_config

        return run(load_config(*argv[1:]))
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
