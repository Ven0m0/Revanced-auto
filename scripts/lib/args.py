"""Argparse subparsers for the CLI."""

import argparse


def build_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Add 'build' subcommand to subparsers."""
    parser = subparsers.add_parser(
        "build",
        help="Build APK with ReVanced patches",
    )
    parser.add_argument(
        "--config",
        default="config.toml",
        help="Path to config TOML file (default: config.toml)",
    )
    parser.add_argument(
        "--build-mode",
        choices=["apk", "module", "both"],
        default="both",
        help="Build mode (default: both)",
    )
    parser.add_argument(
        "--parallel",
        type=int,
        default=1,
        help="Number of parallel jobs (default: 1)",
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        help="Clean before building",
    )
    parser.add_argument(
        "--no-cache",
        action="store_true",
        help="Disable caching",
    )


def check_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Add 'check' subcommand to subparsers."""
    parser = subparsers.add_parser(
        "check",
        help="Check for updates",
    )
    parser.add_argument(
        "--config",
        default="config.toml",
        help="Path to config TOML file (default: config.toml)",
    )


def version_tracker_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Add 'version-tracker' subcommand with sub-subcommands."""
    parser = subparsers.add_parser(
        "version-tracker",
        help="Track and manage version information",
    )
    sub = parser.add_subparsers(dest="version_tracker_command", required=True)

    check = sub.add_parser("check", help="Check version status")
    check.add_argument(
        "--config",
        default="config.toml",
        help="Path to config TOML file (default: config.toml)",
    )

    save = sub.add_parser("save", help="Save current versions")
    save.add_argument(
        "--config",
        default="config.toml",
        help="Path to config TOML file (default: config.toml)",
    )

    show = sub.add_parser("show", help="Show saved versions")
    show.add_argument(
        "--config",
        default="config.toml",
        help="Path to config TOML file (default: config.toml)",
    )

    reset = sub.add_parser("reset", help="Reset version tracker")
    reset.add_argument(
        "--config",
        default="config.toml",
        help="Path to config TOML file (default: config.toml)",
    )


def cache_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Add 'cache' subcommand with sub-subcommands."""
    parser = subparsers.add_parser(
        "cache",
        help="Manage the build cache",
    )
    sub = parser.add_subparsers(dest="cache_command", required=True)

    sub.add_parser("stats", help="Show cache statistics")
    sub.add_parser("init", help="Initialize the cache")

    cleanup = sub.add_parser("cleanup", help="Remove expired cache entries")
    cleanup.add_argument(
        "force_arg",
        nargs="?",
        choices=["force"],
        help="Legacy positional force flag",
    )
    cleanup.add_argument(
        "--force",
        action="store_true",
        help="Also remove orphaned index entries",
    )

    clean = sub.add_parser("clean", help="Remove cache entries matching a regex pattern")
    clean.add_argument(
        "pattern_arg",
        nargs="?",
        help="Legacy positional pattern (default: .*)",
    )
    clean.add_argument(
        "--pattern",
        help="Regex pattern to match cache entries",
    )
