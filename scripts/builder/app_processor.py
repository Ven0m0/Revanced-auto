#!/usr/bin/env python3
"""Application processing module for APK patching workflow.

Orchestrates the complete build process for ReVanced/RVX apps,
replacing the legacy scripts/lib/app_processor.sh implementation.
"""

from __future__ import annotations

import logging
import os
import subprocess
import sys
import tempfile
import urllib.parse
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from types import TracebackType
from typing import TYPE_CHECKING, Any, Protocol, Self

from scripts.builder.cli_profiles import (
    BUILTIN_PROFILES,
    CLIProfile,
    CLIProfileType,
    PatchCommandConfig,
    detect_cli_profile,
)
from scripts.lib.plugins import dispatch_plugins
from scripts.scrapers.base import DownloadSource
from scripts.utils.java import JavaRunner

if TYPE_CHECKING:
    from collections.abc import Callable

    from scripts.builder.config import AppConfig, Config

logger = logging.getLogger(__name__)


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
        value_lower = value.lower()
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


class ReVancedPatcher(Protocol):
    """Protocol for ReVanced patcher implementations."""

    def patch(
        self,
        apk_path: Path,
        output_path: Path,
        patches_jars: list[Path],
        *,
        exclude: list[str] | None = None,
        include: list[str] | None = None,
        merge: list[Path] | None = None,
        keystore: Path | None = None,
        force: bool = False,
        rip_lib: list[str] | None = None,
        options: dict[str, Any] | None = None,
    ) -> subprocess.CompletedProcess[str]:
        """Patch an APK file.

        Args:
            apk_path: Path to input APK.
            output_path: Path to output APK.
            patches_jars: List of patch bundle JAR files.
            exclude: Patches to exclude.
            include: Patches to include.
            merge: Merge JAR files.
            keystore: Keystore for signing.
            force: Force overwrite.
            rip_lib: Libraries to rip.
            options: Additional patcher options.

        Returns:
            CompletedProcess with patch result.
        """
        ...


class VersionResolver(Protocol):
    """Protocol for version resolution implementations."""

    def resolve(
        self,
        app_id: str,
        source: DownloadSource,
        *,
        timeout: int = 300,
    ) -> tuple[str, str]:
        """Resolve app version from download source.

        Args:
            app_id: Application package ID.
            source: Download source to use.
            timeout: Request timeout in seconds.

        Returns:
            Tuple of (version_string, version_code).
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

        Returns:
            Path to downloaded APK.
        """
        ...


class ModuleGenerator(Protocol):
    """Protocol for module generation implementations."""


class Notifier(Protocol):
    """Protocol for build notification implementations."""

    def notify(
        self,
        title: str,
        message: str,
        *,
        success: bool = True,
        results: list[BuildResult] | None = None,
    ) -> None:
        """Send build notification.

        Args:
            title: Notification title.
            message: Notification message.
            success: Whether this is a success notification.
            results: Optional list of build results.
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


def _resolve_github_release_asset(source: str, ext: str, fallback_ext: str | None = None) -> tuple[str, str]:
    """Find the newest GitHub release of ``source`` with a ``.ext`` (or ``.fallback_ext``) asset.

    Ports scripts/lib/prebuilts.sh's resolve_rv_artifact: GitHub's
    ``/releases`` endpoint (not ``/releases/latest``, which excludes
    prereleases) returns releases newest-first, so both "latest" and "dev"
    version modes resolve to whatever's newest -- these repos publish dev
    builds as ordinary (pre-)releases, same as the bash implementation.
    Asset filenames aren't matched by prefix (they vary per fork, e.g.
    MorpheApp's CLI asset is ``morphe-desktop-*-all.jar``, not
    ``morphe-cli-*``); only the newest release's file extension matters.

    Returns:
        Tuple of (asset_filename, asset_api_url). The API asset URL (not
        browser_download_url) requires an octet-stream Accept header to
        stream binary content, which gh_dl() already sets.
    """
    import json

    from scripts.utils.network import gh_req

    releases_raw = gh_req(f"https://api.github.com/repos/{source}/releases")
    releases = json.loads(releases_raw)
    if not releases:
        msg = f"No releases found for {source}"
        raise RuntimeError(msg)

    release = releases[0]
    for candidate_ext in (ext, fallback_ext) if fallback_ext else (ext,):
        for asset in release.get("assets", []):
            name = asset.get("name", "")
            if name.endswith(f".{candidate_ext}"):
                return name, asset["url"]

    tag = release.get("tag_name", "?")
    wanted = f".{ext}" + (f" or .{fallback_ext}" if fallback_ext else "")
    msg = f"No {wanted} asset found in {source} release {tag}"
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


class AppProcessor:
    """Orchestrates the complete build workflow for an app.

    Manages configuration parsing, prebuilt downloads, APK patching,
    and output generation with parallel job execution support.

    Attributes:
        config: Global configuration object.
        java_runner: Java subprocess runner.
        notifier: Optional notification service.
        patcher: Optional ReVanced patcher instance.
        version_resolver: Optional version resolver.
        download_manager: Optional download manager.
        module_generator: Optional module generator.
    """

    def __init__(
        self,
        config: Config,
        java_runner: JavaRunner,
        notifier: Notifier | None = None,
        patcher: ReVancedPatcher | None = None,
        version_resolver: VersionResolver | None = None,
        download_manager: DownloadManager | None = None,
        module_generator: ModuleGenerator | None = None,
    ) -> None:
        """Initialize AppProcessor.

        Args:
            config: Global configuration object.
            java_runner: Java subprocess runner.
            notifier: Optional notification service.
            patcher: Optional ReVanced patcher instance.
            version_resolver: Optional version resolver.
            download_manager: Optional download manager.
            module_generator: Optional module generator.
        """
        self.config = config
        self.java_runner = java_runner
        self.notifier = notifier
        self.patcher = patcher
        self.version_resolver = version_resolver
        self.download_manager = download_manager
        self.module_generator = module_generator

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

        with JobRunner(max_workers=self.parallel_jobs) as runner:
            futures: dict[Future[BuildResult], str] = {}

            for app_config in enabled_apps:
                arch = self._parse_architecture(app_config)
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

        if self.notifier:
            self._send_notification(summary)

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
        if version == "auto" and self.version_resolver:
            version, candidates = self._resolve_version_with_failover(candidates)

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
    ) -> tuple[str, list[tuple[DownloadSource, str]]]:
        """Resolve ``version == "auto"`` by trying each candidate source in order.

        Returns the resolved version and ``candidates`` reordered so the
        source that resolved comes first, followed by the rest in their
        original order -- so a later download failure can still fail over.
        """
        if self.version_resolver is None:
            msg = "No version resolver configured"
            raise RuntimeError(msg)

        errors: list[str] = []
        for i, (source, download_url) in enumerate(candidates):
            pkg_name = _derive_scraper_pkg_name(download_url, source) if download_url else ""
            try:
                version, _ = self.version_resolver.resolve(pkg_name, source)
            except Exception as e:
                errors.append(f"{source.value}: {e}")
                continue
            return version, [candidates[i], *candidates[:i], *candidates[i + 1 :]]

        msg = f"Failed to resolve version from any configured source: {'; '.join(errors)}"
        raise RuntimeError(msg)

    def _execute_build(self, context: AppBuildContext) -> BuildResult:
        """Execute the actual build process.

        Args:
            context: Build context.

        Returns:
            BuildResult of the build.
        """
        dispatch_plugins(context, "pre_pipeline")

        stock_apk = self._download_stock_apk(context)

        cli_jar, patches_jars = self._ensure_prebuilts(context)
        context.cli_jar = cli_jar
        context.patches_jars = patches_jars
        changelog = self._get_changelog(context)
        patched_apk = self._run_patcher(context, stock_apk)

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
        """Download stock APK.

        Args:
            context: Build context.

        Returns:
            Path to downloaded APK.
        """
        if self.download_manager:
            candidates = context.candidates or [(context.source, context.download_url)]
            output_path = Path(tempfile.gettempdir()) / f"stock-{context.app_name}-{context.version}.apk"
            errors: list[str] = []
            for source, download_url in candidates:
                pkg_name = _derive_scraper_pkg_name(download_url, source) if download_url else context.app_id
                try:
                    return self.download_manager.download(
                        pkg_name,
                        context.version,
                        output_path,
                        source,
                        arch=context.arch,
                    )
                except Exception as e:
                    logger.warning("Download from %s failed for %s: %s", source.value, context.app_name, e)
                    errors.append(f"{source.value}: {e}")
            msg = f"Failed to download stock APK for {context.app_name} from any source: {'; '.join(errors)}"
            raise RuntimeError(msg)

        download_url = context.download_url
        if not download_url:
            raise ValueError(f"No download URL available for {context.app_name}")

        temp_dir = Path(tempfile.gettempdir())
        stock_path = temp_dir / f"stock-{context.app_name}-{context.version}.apk"

        from scripts.utils.network import download_with_lock

        success = download_with_lock(download_url, stock_path)
        if not success:
            raise RuntimeError(f"Failed to download stock APK from {download_url}")

        return stock_path

    def _ensure_prebuilts(
        self,
        context: AppBuildContext,
    ) -> tuple[Path, list[Path]]:
        """Ensure CLI and patches JARs are downloaded.

        Args:
            context: Build context.

        Returns:
            Tuple of (cli_jar_path, patches_jars_paths).
        """
        cache_dir = Path(os.environ.get("CACHE_DIR", ".cache"))
        prebuilts_dir = cache_dir / "prebuilts"
        prebuilts_dir.mkdir(parents=True, exist_ok=True)

        cli_jar = prebuilts_dir / f"cli-{context.cli_version}.jar"
        patches_jars: list[Path] = []

        from scripts.utils.network import gh_dl

        if not cli_jar.exists():
            _asset_name, cli_url = _resolve_github_release_asset(context.cli_source, "jar")
            success = gh_dl(cli_jar, cli_url)
            if not success:
                raise RuntimeError(f"Failed to download CLI from {context.cli_source}")

        patches_sources = (
            [context.patches_source] if isinstance(context.patches_source, str) else context.patches_source
        )

        from scripts.scrapers.external_bundles import (
            is_external_bundles_source,
            parse_bundle_selector,
            resolve_bundle,
        )

        for idx, patches_src in enumerate(patches_sources):
            is_morphe = _is_morphe_patches_source(patches_src)
            ext = "mpp" if is_morphe else "rvp"
            patches_jar = prebuilts_dir / f"patches-{context.patches_version}-{idx}.{ext}"
            patches_jars.append(patches_jar)

            if patches_jar.exists():
                continue

            if is_external_bundles_source(patches_src):
                selector = parse_bundle_selector(patches_src) or context.app_id
                entry = resolve_bundle(selector, context.patches_version)
                patches_url = entry.download_url
            else:
                fallback_ext = "rvp" if is_morphe else "mpp"
                _asset_name, patches_url = _resolve_github_release_asset(patches_src, ext, fallback_ext)

            success = gh_dl(patches_jar, patches_url)
            if not success:
                raise RuntimeError(f"Failed to download patches from {patches_url}")

        return cli_jar, patches_jars

    def _get_changelog(self, context: AppBuildContext) -> list[str]:
        """Get list of patches that will be applied.

        Args:
            context: Build context.

        Returns:
            List of patch names.
        """
        if not context.cli_jar:
            return []

        cli_profile = self._resolve_cli_profile(context)
        list_args = cli_profile.build_list_patches_args(context.patches_jars)

        try:
            result = self.java_runner.run_jar(
                str(context.cli_jar),
                list_args,
                timeout=60,
            )
            if result.returncode == 0:
                lines = result.stdout.splitlines()
                return [line.strip() for line in lines if line.strip()]
        except Exception as e:
            logger.warning("Failed to get changelog: %s", e)

        return []

    def _run_patcher(
        self,
        context: AppBuildContext,
        stock_apk: Path,
    ) -> Path:
        """Run the ReVanced patcher.

        Args:
            context: Build context.
            stock_apk: Path to stock APK.

        Returns:
            Path to patched APK.
        """
        if self.patcher:
            _alias, keystore_password, _entry_password, _signer = self._get_keystore_credentials()
            keystore = self._get_keystore_path(keystore_password)
            result = self.patcher.patch(
                stock_apk,
                context.output_path,
                context.patches_jars,
                exclude=context.excluded_patches if not context.exclusive_patches else None,
                include=context.included_patches if context.exclusive_patches else None,
                keystore=keystore,
                rip_lib=[] if context.riplib else None,
                options=context.patch_options or None,
            )
            if result.returncode != 0:
                raise RuntimeError(f"Patching failed: {result.stderr}")
            return context.output_path

        cli_profile = self._resolve_cli_profile(context)
        alias, keystore_password, keystore_entry_password, signer = self._get_keystore_credentials()
        keystore = self._get_keystore_path(keystore_password)
        riplib_libs: list[str] = []
        if context.riplib and self._profile_supports_riplib(cli_profile):
            keep_semantics = cli_profile.profile_type in (CLIProfileType.MORPHE_CLI, CLIProfileType.ADOBO_CLI)
            riplib_libs = _riplib_values(context.arch, keep_semantics=keep_semantics)

        patch_config = PatchCommandConfig(
            apk_path=stock_apk,
            output_path=context.output_path,
            patches_jars=context.patches_jars,
            exclude=context.excluded_patches if not context.exclusive_patches else [],
            include=context.included_patches if context.exclusive_patches else [],
            merge=context.merge_patches,
            keystore=keystore,
            keystore_alias=alias,
            keystore_password=keystore_password,
            keystore_entry_password=keystore_entry_password,
            signer=signer,
            rip_lib=riplib_libs,
            exclusive=context.exclusive_patches,
            options=context.patch_options,
        )
        patch_args = cli_profile.build_patch_args(patch_config)

        result = self.java_runner.run_jar(
            str(context.cli_jar),
            patch_args,
            timeout=600,
        )

        if result.returncode != 0:
            raise RuntimeError(f"Patching failed: {result.stderr}")

        return context.output_path

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

    def _get_keystore_path(self, keystore_password: str) -> Path | None:
        """Get keystore path from configuration, converted to BKS if necessary.

        Morphe's patcher only accepts BKS keystores and converts anything
        else via a BouncyCastle copy whose jar signature it rejects (the
        "JCE cannot authenticate the provider BC" failure) -- converting
        once here up front avoids ever handing it a non-BKS keystore.

        Args:
            keystore_password: Password for the keystore, needed for conversion.

        Returns:
            Path to a BKS keystore, or None if none is configured.
        """
        from scripts.utils.keystore import ensure_bks

        if self.config.global_settings.keystore_path:
            keystore = Path(self.config.global_settings.keystore_path)
        else:
            default_keystore = Path("assets/ks.keystore")
            if not default_keystore.exists():
                return None
            keystore = default_keystore

        return ensure_bks(keystore, keystore_password)

    def _get_keystore_credentials(self) -> tuple[str, str, str, str]:
        """Get keystore alias/passwords/signer.

        Default alias is lowercase "morphe": `keytool -genkeypair` always
        lowercases the alias it stores regardless of the case passed to
        `-alias` (confirmed: `keytool -list` on assets/ks.keystore, generated
        with `-alias Morphe`, shows the entry as "morphe"), and
        morphe-desktop's own alias lookup is exact-match, not the
        case-insensitive lookup java.security.KeyStore itself does --
        confirmed live: "Keystore does not contain entry with alias Morphe"
        even though standard KeyStore.getKey("Morphe", ...) resolves fine.
        Falls back to KEYSTORE_PASSWORD/KEYSTORE_ENTRY_PASSWORD env vars
        (already set by the CI workflows) or GlobalConfig.keystore_alias
        first, so a real production keystore + secrets can override this
        without a code change.

        Returns:
            Tuple of (keystore_alias, keystore_password, keystore_entry_password, signer).
        """
        alias = self.config.global_settings.keystore_alias or "morphe"
        keystore_password = os.environ.get("KEYSTORE_PASSWORD") or "Morphe"
        keystore_entry_password = os.environ.get("KEYSTORE_ENTRY_PASSWORD") or "Morphe"
        return alias, keystore_password, keystore_entry_password, alias

    def _parse_architecture(self, app_config: AppConfig) -> Architecture:
        """Parse architecture from app config.

        Args:
            app_config: App configuration.

        Returns:
            Architecture enum value.
        """
        arch_str = app_config.options.get("arch", "all")
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

    def _send_notification(self, summary: BuildSummary) -> None:
        """Send a build completion notification."""
        if not self.notifier:
            return

        title = f"Build {'Succeeded' if summary.failure_count == 0 else 'Failed'}"
        message = f"Built {summary.success_count}/{summary.total} apps in {summary.duration:.1f}s"

        self.notifier.notify(
            title,
            message,
            success=summary.failure_count == 0,
            results=summary.succeeded + summary.failed,
        )


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
        from scripts.scrapers.download_manager import DownloadManager

        config = load_config(*argv[1:])

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

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
