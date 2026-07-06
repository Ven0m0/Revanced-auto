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
from scripts.builder.engines import EngineContext, EngineRunner, EngineStage
from scripts.lib.plugins import dispatch_plugins

if TYPE_CHECKING:
    from collections.abc import Callable

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


class DownloadSource(Enum):
    """Supported download sources for stock APKs."""

    APKPURE = "apkpure"
    APKMIRROR = "apkmirror"
    UPTODOWN = "uptodown"
    ARCHIVE = "archive"
    APTOIDE = "aptoide"
    APKMonk = "apkmonk"


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

    def generate(
        self,
        apk_paths: list[Path],
        output_path: Path,
        *,
        module_name: str | None = None,
        options: dict[str, Any] | None = None,
    ) -> Path:
        """Generate a module ZIP from patched APKs.

        Args:
            apk_paths: List of patched APK paths.
            output_path: Where to save the module ZIP.
            module_name: Optional module name.
            options: Additional generation options.

        Returns:
            Path to generated module ZIP.
        """
        ...


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


def _cli_artifact_name(cli_source: str) -> str:
    """Derive the CLI JAR artifact prefix from a ``owner/repo`` slug.

    Examples:
        ``MorpheApp/morphe-cli`` → ``morphe-cli``
        ``ReVanced/revanced-cli`` → ``revanced-cli``
        ``inotia00/revanced-cli`` → ``revanced-cli``
    """
    return cli_source.strip().rstrip("/").rsplit("/", 1)[-1]


def _patches_artifact_name(patches_source: str) -> str:
    """Derive the patches JAR artifact prefix from a ``owner/repo`` slug.

    Examples:
        ``MorpheApp/morphe-patches`` → ``morphe-patches``
        ``ReVanced/revanced-patches`` → ``revanced-patches``
        ``crimera/piko`` → ``piko``
    """
    return patches_source.strip().rstrip("/").rsplit("/", 1)[-1]


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
        source: Download source.
        download_url: Pre-configured download URL.
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
    """

    app_name: str
    app_id: str
    brand: str
    version: str
    arch: str
    output_path: Path
    source: DownloadSource
    download_url: str = ""
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
    engine_options: dict[str, Any] = field(default_factory=dict)


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
        self._job_runner: JobRunner | None = None

    @property
    def parallel_jobs(self) -> int:
        """Get configured parallel job count."""
        return self.config.global_settings.parallel_jobs or 2

    def process_app(self, app_config: AppConfig) -> list[BuildResult]:
        """Process a single app configuration.

        Returns list of build results (one per architecture).

        Args:
            app_config: App configuration to process.

        Returns:
            List of BuildResult objects for each architecture build.
        """
        if not app_config.enabled:
            logger.info("Skipping disabled app: %s", app_config.name)
            return []

        logger.info("Processing app: %s", app_config.name)

        arch = self._parse_architecture(app_config)
        arch_list = self._get_architecture_list(arch)

        results: list[BuildResult] = []
        for arch_variant in arch_list:
            result = self._build_app_variant(app_config, arch_variant)
            results.append(result)

        return results

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
            futures: dict[Future[list[BuildResult]], str] = {}

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
                    results = future.result()
                    all_results.extend(results)
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
            result.build_time = time.time() - start_time
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
        source = self._determine_download_source(app_config)

        download_url = self._get_download_url(app_config, source)

        version = app_config.version or "auto"
        if version == "auto" and self.version_resolver:
            version, _ = self.version_resolver.resolve(app_config.name, source)

        patches_source = app_config.patches_source or self.config.global_settings.patches_source
        patches_version = self.config.global_settings.patches_version

        cli_source = app_config.cli_source or self.config.global_settings.cli_source
        cli_version = self.config.global_settings.cli_version

        output_dir = Path("build")
        output_dir.mkdir(exist_ok=True)

        output_name = f"{app_name}-{version}-{arch}"
        output_path = output_dir / f"{output_name}.apk"

        # Extract engine-specific sub-tables from options so engines receive
        # their own options cleanly. Remaining options stay as patcher options.
        engine_names = [
            "media_optimizer",
            "apk_optimizer",
            "string_cleaner",
            "dtlx",
            "lspatch",
            "rkpairip",
            "whatsapp_patcher",
        ]
        engine_options: dict[str, Any] = {}
        remaining_options = app_config.options.copy()
        for engine_name in engine_names:
            if engine_name in remaining_options:
                engine_options[engine_name] = remaining_options.pop(engine_name)

        return AppBuildContext(
            app_name=app_name,
            app_id=app_config.name,
            brand=brand,
            version=version,
            arch=arch,
            output_path=output_path,
            source=source,
            download_url=download_url,
            patches_source=patches_source,
            patches_version=patches_version,
            cli_source=cli_source,
            cli_version=cli_version,
            excluded_patches=app_config.exclude_patches,
            included_patches=app_config.patches,
            exclusive_patches=app_config.exclusive,
            riplib=self.config.global_settings.riplib,
            options=remaining_options,
            engine_options=engine_options,
        )

    def _execute_build(self, context: AppBuildContext) -> BuildResult:
        """Execute the actual build process.

        Args:
            context: Build context.

        Returns:
            BuildResult of the build.
        """
        pipeline_ctx = self._build_pipeline_context(context, context.output_path.parent)
        dispatch_plugins(pipeline_ctx, "pre_pipeline")

        stock_apk = self._download_stock_apk(context)

        # Run pre-patch engines (e.g., LSPatch, DTL-X, RKPairip)
        current_apk = self._run_engines(context, stock_apk, EngineStage.PRE_PATCH)

        # Determine whether to skip ReVanced patching when LSPatch is in
        # alternative mode.
        lspatch_mode = context.engine_options.get("lspatch", {}).get("mode", "complement")
        skip_revanced = (
            self._is_engine_enabled(context, "lspatch")
            and lspatch_mode == "alternative"
        )

        if skip_revanced:
            patched_apk = current_apk
            changelog: list[str] = []
        else:
            cli_jar, patches_jars = self._ensure_prebuilts(context)
            context.cli_jar = cli_jar
            context.patches_jars = patches_jars
            changelog = self._get_changelog(context)
            patched_apk = self._run_patcher(context, current_apk)

        # Run post-patch engines (e.g., Media Optimizer, APK Optimizer, String Cleaner)
        final_apk = self._run_engines(context, patched_apk, EngineStage.POST_PATCH)

        dispatch_plugins(pipeline_ctx, "post_pipeline")

        return BuildResult(
            app_name=context.app_name,
            brand=context.brand,
            version=context.version,
            arch=context.arch,
            output_path=final_apk,
            success=True,
            changelog=changelog,
        )

    def _is_engine_enabled(self, context: AppBuildContext, engine_name: str) -> bool:
        """Check if an engine is enabled for the current app.

        Args:
            context: Build context.
            engine_name: Engine identifier.

        Returns:
            True if the engine should run.
        """
        from scripts.builder.config import AppConfig

        app_config = self.config.apps.get(context.app_id)
        if not isinstance(app_config, AppConfig):
            return False

        global_value = getattr(self.config.global_settings, f"enable_{engine_name}", False)
        return app_config.engine_enabled(engine_name, global_value)

    def _run_engines(
        self,
        context: AppBuildContext,
        input_apk: Path,
        stage: EngineStage,
    ) -> Path:
        """Run all enabled engines for a pipeline stage.

        Args:
            context: Build context.
            input_apk: Input APK path for this stage.
            stage: Pipeline stage to execute.

        Returns:
            Path to the APK after engines have run.
        """
        enabled_engines = [
            name
            for name in [
                "media_optimizer",
                "apk_optimizer",
                "string_cleaner",
                "dtlx",
                "lspatch",
                "rkpairip",
                "whatsapp_patcher",
            ]
            if self._is_engine_enabled(context, name)
        ]

        if not enabled_engines:
            return input_apk

        work_dir = context.output_path.parent / "engine_work" / context.app_id / stage.value
        work_dir.mkdir(parents=True, exist_ok=True)

        engine_ctx = EngineContext(
            app_name=context.app_name,
            app_id=context.app_id,
            version=context.version,
            arch=context.arch,
            current_apk=input_apk,
            output_dir=context.output_path.parent,
            work_dir=work_dir,
            global_options={
                "lspatch_mode": context.engine_options.get("lspatch", {}).get("mode", "complement"),
            },
            app_options=context.engine_options,
        )

        runner = EngineRunner(stage, enabled_engines)
        return runner.run(engine_ctx)

    def _build_pipeline_context(
        self,
        context: AppBuildContext,
        output_dir: Path,
    ) -> EngineContext:
        """Create an EngineContext for plugin hooks.

        Args:
            context: App build context.
            output_dir: Output directory for artifacts.

        Returns:
            EngineContext for plugin dispatch.
        """
        return EngineContext(
            app_name=context.app_name,
            app_id=context.app_id,
            version=context.version,
            arch=context.arch,
            current_apk=context.output_path,
            output_dir=output_dir,
            work_dir=output_dir / "engine_work" / context.app_id,
            global_options={},
            app_options=context.engine_options,
        )

    def _download_stock_apk(self, context: AppBuildContext) -> Path:
        """Download stock APK.

        Args:
            context: Build context.

        Returns:
            Path to downloaded APK.
        """
        if self.download_manager:
            return self.download_manager.download(
                context.app_id,
                context.version,
                context.output_path.parent / f"stock-{context.app_name}-{context.version}.apk",
                context.source,
                arch=context.arch,
            )

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
            cli_artifact = _cli_artifact_name(context.cli_source)
            cli_url = (
                f"https://github.com/{context.cli_source}/releases/download/"
                f"v{context.cli_version}/{cli_artifact}-{context.cli_version}-all.jar"
            )
            success = gh_dl(cli_jar, cli_url)
            if not success:
                raise RuntimeError(f"Failed to download CLI from {cli_url}")

        patches_sources = (
            [context.patches_source] if isinstance(context.patches_source, str) else context.patches_source
        )

        from scripts.scrapers.external_bundles import (
            is_external_bundles_source,
            parse_bundle_selector,
            resolve_bundle,
        )

        for idx, patches_src in enumerate(patches_sources):
            patches_jar = prebuilts_dir / f"patches-{context.patches_version}-{idx}.jar"
            patches_jars.append(patches_jar)

            if patches_jar.exists():
                continue

            if is_external_bundles_source(patches_src):
                selector = parse_bundle_selector(patches_src) or context.app_id
                entry = resolve_bundle(selector, context.patches_version)
                patches_url = entry.download_url
            else:
                patches_artifact = _patches_artifact_name(patches_src)
                patches_url = (
                    f"https://github.com/{patches_src}/releases/download/v{context.patches_version}/"
                    f"{patches_artifact}-{context.patches_version}.jar"
                )

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
                ["list-patches"] + list_args,
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
            keystore = self._get_keystore_path()
            result = self.patcher.patch(
                stock_apk,
                context.output_path,
                context.patches_jars,
                exclude=context.excluded_patches if not context.exclusive_patches else None,
                include=context.included_patches if context.exclusive_patches else None,
                keystore=keystore,
                rip_lib=list(context.riplib) if context.riplib else None,
            )
            if result.returncode != 0:
                raise RuntimeError(f"Patching failed: {result.stderr}")
            return context.output_path

        cli_profile = self._resolve_cli_profile(context)
        keystore = self._get_keystore_path()
        riplib_libs: list[str] = []
        if context.riplib and self._profile_supports_riplib(cli_profile):
            riplib_libs = []

        patch_config = PatchCommandConfig(
            apk_path=stock_apk,
            output_path=context.output_path,
            patches_jars=context.patches_jars,
            exclude=context.excluded_patches if not context.exclusive_patches else [],
            include=context.included_patches if context.exclusive_patches else [],
            merge=context.merge_patches,
            keystore=keystore,
            rip_lib=riplib_libs,
        )
        patch_args = cli_profile.build_patch_args(patch_config)

        if context.riplib and self._profile_supports_riplib(cli_profile):
            riplib_mapping = cli_profile.patch_args.get("RIP_LIB")
            if riplib_mapping:
                patch_args.extend(riplib_mapping.prepend_args)
                patch_args.append(riplib_mapping.flag)

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
            except Exception as e:  # noqa: BLE001 - detection is best-effort
                logger.debug("CLI profile detection failed (%s); using MORPHE_CLI", e)

        return BUILTIN_PROFILES[CLIProfileType.MORPHE_CLI]

    @staticmethod
    def _profile_supports_riplib(profile: CLIProfile) -> bool:
        """Return True when the profile declares a RIP_LIB arg mapping."""
        return "RIP_LIB" in profile.patch_args and profile.patch_args["RIP_LIB"] is not None

    def _get_keystore_path(self) -> Path | None:
        """Get keystore path from configuration.

        Returns:
            Path to keystore or None.
        """
        if self.config.global_settings.keystore_path:
            return Path(self.config.global_settings.keystore_path)

        default_keystore = Path("assets/ks.keystore")
        if default_keystore.exists():
            return default_keystore

        return None

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

    def _determine_download_source(self, app_config: AppConfig) -> DownloadSource:
        """Determine download source from app config.

        Args:
            app_config: App configuration.

        Returns:
            DownloadSource enum value.
        """
        options = app_config.options

        if options.get("apkmirror_dlurl"):
            return DownloadSource.APKMIRROR
        if options.get("uptodown_dlurl"):
            return DownloadSource.UPTODOWN
        if options.get("apkpure_dlurl"):
            return DownloadSource.APKPURE
        if options.get("archive_dlurl"):
            return DownloadSource.ARCHIVE
        if options.get("aptoide_dlurl"):
            return DownloadSource.APTOIDE
        if options.get("apkmonk_dlurl"):
            return DownloadSource.APKMonk

        return DownloadSource.APKMIRROR

    def _get_download_url(self, app_config: AppConfig, source: DownloadSource) -> str:
        """Get download URL from app config.

        Args:
            app_config: App configuration.
            source: Download source.

        Returns:
            Download URL string.
        """
        options = app_config.options

        url_map = {
            DownloadSource.APKMIRROR: options.get("apkmirror_dlurl", ""),
            DownloadSource.UPTODOWN: options.get("uptodown_dlurl", ""),
            DownloadSource.APKPURE: options.get("apkpure_dlurl", ""),
            DownloadSource.ARCHIVE: options.get("archive_dlurl", ""),
            DownloadSource.APTOIDE: options.get("aptoide_dlurl", ""),
            DownloadSource.APKMonk: options.get("apkmonk_dlurl", ""),
        }

        return url_map.get(source, "")

    def _send_notification(self, summary: BuildSummary) -> None:
        """Send build completion notification.

        Args:
            summary: Build summary.
        """
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

    def generate_changelog(
        self,
        results: list[BuildResult],
    ) -> str:
        """Generate changelog from build results.

        Args:
            results: List of build results.

        Returns:
            Markdown-formatted changelog string.
        """
        lines = ["# Changelog\n"]

        for result in results:
            if not result.success:
                continue

            lines.append(f"## {result.app_name} {result.version} ({result.arch})")
            lines.append("")

            if result.changelog:
                for patch in result.changelog:
                    lines.append(f"- {patch}")
            else:
                lines.append("_No patches listed_")

            lines.append("")

        return "\n".join(lines)


class Config:
    """Placeholder for Config type. Actual type is from config module."""

    global_settings: GlobalConfig
    apps: dict[str, AppConfig]


class GlobalConfig:
    """Placeholder for GlobalConfig type."""

    parallel_jobs: int = 0
    build_mode: str = "apk"
    patches_version: str = "latest"
    cli_version: str = "latest"
    patches_source: str | list[str] = "MorpheApp/morphe-patches"
    riplib: bool = True
    keystore_path: str | None = None


class AppConfig:
    """Placeholder for AppConfig type."""

    name: str
    enabled: bool = True
    version: str | None = None
    patches_source: str | list[str] | None = None
    patches: list[str] = field(default_factory=list)
    exclude_patches: list[str] = field(default_factory=list)
    exclusive: bool = False
    options: dict[str, Any] = field(default_factory=dict)


class JavaRunner:
    """Placeholder for JavaRunner type. Actual type is from utils.java module."""

    def run(
        self,
        args: list[str],
        *,
        timeout: int | None = None,
    ) -> subprocess.CompletedProcess[str]:
        """Run a subprocess."""

    def run_jar(
        self,
        jar_path: str,
        jar_args: list[str],
        *,
        timeout: int | None = None,
    ) -> subprocess.CompletedProcess[str]:
        """Run a JAR file."""


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

        config = load_config(*argv[1:])
        from scripts.utils.java import JavaRunner

        processor = AppProcessor(config, JavaRunner())

        summary = processor.process_all()

        print(f"Built {summary.success_count}/{summary.total} apps")
        if summary.failed:
            print("Failed apps:")
            for result in summary.failed:
                print(f"  - {result.app_name}: {result.error}")

        return 0 if summary.failure_count == 0 else 1

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
