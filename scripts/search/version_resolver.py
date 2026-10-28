"""Parsers for Morphe CLI ``list-versions`` and ``list-patches`` output."""

from __future__ import annotations

import re

_VERSION_LINE = re.compile(r"^\s*(\d+(?:\.\d+)+)\b")
_PATCH_NAME_LINE = re.compile(r"^\s*(?:INFO:\s*)?Name:\s*(.+?)\s*$")


def parse_versions(output: str) -> list[str]:
    """Return the app versions listed in ``list-versions`` output, de-duplicated, in order."""
    versions = (m.group(1) for line in output.splitlines() if (m := _VERSION_LINE.match(line)))
    return list(dict.fromkeys(versions))


def parse_patch_names(output: str) -> list[str]:
    """Return the patch names listed in ``list-patches`` output, in order."""
    return [m.group(1) for line in output.splitlines() if (m := _PATCH_NAME_LINE.match(line))]
