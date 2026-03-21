#!/usr/bin/env python3
"""CLI entry point for ReVanced Builder."""

import argparse
import signal
import sys
from typing import Optional

from scripts.lib import logging as log
from scripts.lib.args import (
    build_parser,
    check_parser,
    version_tracker_parser,
)
from scripts.lib.config import Config
from scripts.lib.version_tracker import VersionTracker


def _signal_handler(signum: int, frame) -> None:
    """Handle interrupt signals gracefully."""
    signame = signal.Signals(signum).name
    log.abort(f"Received {signame}, shutting down...", code=130)


def run_build(args: argparse.Namespace) -> int:
    """Execute the build command."""
    config_path = args.config

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

    args = parser.parse_args()

    try:
        if args.command == "build":
            return run_build(args)
        elif args.command == "check":
            return run_check(args)
        elif args.command == "version-tracker":
            return run_version_tracker(args)
        else:
            parser.print_help()
            return 1
    except KeyboardInterrupt:
        log.abort("Interrupted", code=130)


if __name__ == "__main__":
    sys.exit(main())
