#!/usr/bin/env python3
"""CLI entry point for ReVanced Builder."""

import argparse
import re
import signal
import sys
from pathlib import Path

# Allow running as a direct script: `python scripts/cli.py`
# Inserts the project root so `scripts.*` imports resolve correctly.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.lib import logging as log
from scripts.lib.args import (
    build_parser,
    cache_parser,
    check_parser,
    version_tracker_parser,
)
from scripts.lib.cache import (
    CacheError,
    CacheManager,
    format_cache_size,
)


def _signal_handler(signum: int, frame) -> None:
    """Handle interrupt signals gracefully."""
    signame = signal.Signals(signum).name
    log.abort(f"Received {signame}, shutting down...", code=130)


def run_build(args: argparse.Namespace) -> int:
    """Execute the build command."""
    config_path = args.config
    from scripts.lib.config import Config
    from scripts.lib.version_tracker import VersionTracker

    try:
        config = Config.from_file(config_path)
    except FileNotFoundError:
        log.abort(f"Config file not found: {config_path}")
    except Exception as e:
        log.abort(f"Failed to load config: {e}")

    if args.build_mode:
        config.build_mode = args.build_mode
    if args.parallel is not None:
        config.parallel_jobs = args.parallel
    if args.no_cache:
        config.use_cache = False

    version_tracker = VersionTracker(config)

    log.info("Checking versions...")
    needs_build = version_tracker.check()
    if not needs_build:
        log.info("All apps are up to date, skipping build")
        return 0

    if args.clean:
        log.info("Cleaning build directories...")
        config.clean()

    log.info("Starting build...")
    try:
        from scripts.lib.builder import Builder

        builder = Builder(config)
        success = builder.build_all()

        if success:
            version_tracker.save()
            log.info("Build completed successfully")
            return 0
        else:
            log.abort("Build failed")
    except Exception as e:
        log.abort(f"Build error: {e}")


def run_check(args: argparse.Namespace) -> int:
    """Execute the check command."""
    config_path = args.config
    from scripts.lib.config import Config
    from scripts.lib.version_tracker import VersionTracker

    try:
        config = Config.from_file(config_path)
    except FileNotFoundError:
        log.abort(f"Config file not found: {config_path}")
    except Exception as e:
        log.abort(f"Failed to load config: {e}")

    version_tracker = VersionTracker(config)

    log.info("Checking versions...")
    needs_build = version_tracker.check()

    if needs_build:
        log.info("Updates available, build needed")
        return 0
    else:
        log.info("All apps are up to date")
        return 0


def run_version_tracker(args: argparse.Namespace) -> int:
    """Execute version tracker subcommands."""
    config_path = args.config
    from scripts.lib.config import Config
    from scripts.lib.version_tracker import VersionTracker

    try:
        config = Config.from_file(config_path)
    except FileNotFoundError:
        log.abort(f"Config file not found: {config_path}")
    except Exception as e:
        log.abort(f"Failed to load config: {e}")

    version_tracker = VersionTracker(config)
    subcommand = args.version_tracker_command

    if subcommand == "check":
        log.info("Checking versions...")
        needs_build = version_tracker.check()
        if needs_build:
            log.info("Updates available, build needed")
        else:
            log.info("All apps are up to date")
        return 0

    elif subcommand == "save":
        log.info("Saving version state...")
        version_tracker.save()
        log.info("Version state saved")
        return 0

    elif subcommand == "show":
        state = version_tracker.get_state()
        if state:
            log.info("Current version state:")
            for app, version in state.items():
                log.info(f"  {app}: {version}")
        else:
            log.info("No version state recorded")
        return 0

    elif subcommand == "reset":
        log.info("Resetting version state...")
        version_tracker.reset()
        log.info("Version state reset")
        return 0

    else:
        log.abort(f"Unknown subcommand: {subcommand}")


def run_cache(args: argparse.Namespace) -> int:
    """Execute cache subcommands."""
    manager = CacheManager()
    subcommand = args.cache_command

    try:
        if subcommand == "stats":
            stats = manager.cache_stats()
            log.pr("Cache Statistics:")
            log.pr(f"  Total entries: {stats.total_entries}")
            log.pr(f"  Total size: {format_cache_size(stats.total_size)}")
            log.pr(f"  Expired entries: {stats.expired_entries}")
            log.pr(f"  Cache directory: {stats.cache_directory}")
            return 0

        if subcommand == "init":
            manager.cache_init()
            log.pr("Cache initialized")
            return 0

        if subcommand == "cleanup":
            force = args.force or args.force_arg == "force"
            result = manager.cache_cleanup(force=force)
            if result.removed_entries > 0:
                log.pr(f"Removed {result.removed_entries} expired cache entries")
            else:
                log.info("No expired entries to remove")

            if force and result.orphaned_entries > 0:
                log.pr(f"Removed {result.orphaned_entries} orphaned index entries")
            elif force:
                log.info("No orphaned index entries to remove")
            return 0

        if subcommand == "clean":
            pattern = args.pattern or args.pattern_arg or ".*"
            removed_entries = manager.cache_clean_pattern(pattern)
            if removed_entries > 0:
                log.pr(f"Removed {removed_entries} cache entries")
            else:
                log.info("No matching entries found")
            return 0

        log.abort(f"Unknown cache subcommand: {subcommand}")
    except (CacheError, OSError, re.error) as exc:
        log.abort(f"Cache command failed: {exc}")


def main() -> int:
    """Main entry point."""
    signal.signal(signal.SIGINT, _signal_handler)
    signal.signal(signal.SIGTERM, _signal_handler)

    parser = argparse.ArgumentParser(
        prog="python -m scripts.cli",
        description="ReVanced Builder CLI",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    build_parser(subparsers)
    check_parser(subparsers)
    version_tracker_parser(subparsers)
    cache_parser(subparsers)

    args = parser.parse_args()

    try:
        if args.command == "build":
            return run_build(args)
        elif args.command == "check":
            return run_check(args)
        elif args.command == "version-tracker":
            return run_version_tracker(args)
        elif args.command == "cache":
            return run_cache(args)
        else:
            parser.print_help()
            return 1
    except KeyboardInterrupt:
        log.abort("Interrupted", code=130)


if __name__ == "__main__":
    sys.exit(main())
