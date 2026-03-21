"""Argparse subparsers for the CLI."""

import argparse


def build_parser(subparsers: argparse._SubParsersAction) -> None:
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


def check_parser(subparsers: argparse._SubParsersAction) -> None:
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


def version_tracker_parser(subparsers: argparse._SubParsersAction) -> None:
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
