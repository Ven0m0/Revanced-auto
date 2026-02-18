#!/usr/bin/env python3
"""Changelog parser for git commit history.

This script reads git commit metadata from standard input, categorizes each
commit using the Conventional Commits format when possible, and falls back to
simple keyword heuristics otherwise. The categorized commits are written to
standard output in a machine-readable, unit-separator-delimited format.

Input format
------------
Each input line is expected to contain five fields separated by the ASCII
Unit Separator character (``\\x1f``), typically produced by a ``git log``
command such as::

    git log --pretty=format:'%H%x1f%s%x1f%an%x1f%b%x1f%ad'

The fields, in order, are:

1. ``hash``: Full commit hash
2. ``subject``: The commit subject line
3. ``author``: Commit author name
4. ``body``: Commit body (currently ignored by this parser)
5. ``date``: Commit date string

Categorization
--------------
The parser first attempts to interpret the commit subject as a Conventional
Commit of the form ``type(scope): description``. If successful, ``type`` is
mapped to a high-level category (for example, ``feat`` -> ``features``,
``fix`` -> ``fixes``) and ``scope`` and ``description`` are extracted.

If the subject does not match the Conventional Commits pattern, the parser
uses simple keyword heuristics to assign the commit to categories such as
``features``, ``fixes``, ``updates``, ``improvements``, ``removals``, or
``security``. Commits that do not match any known pattern are categorized as
``other``.

Output format
-------------
For each valid input line, the script prints a single line to standard output,
using the Unit Separator (``\\x1f``) as a field delimiter, with fields in the
following order:

1. ``category``: High-level category name
2. ``scope``: Optional scope extracted from the subject (empty if none)
3. ``description``: Commit description (subject without the ``type(scope):``)
4. ``hash``: Full commit hash
5. ``author``: Commit author name
6. ``date``: Commit date string

The script is intended to be used in a pipeline, for example::

    git log --pretty=format:'%H%x1f%s%x1f%an%x1f%b%x1f%ad' \\
        | python3 scripts/changelog_parser.py

Any malformed lines or unexpected errors are reported to standard error and
skipped, so that processing of the remaining commits can continue.
"""
import re
import sys


def parse_commits() -> None:
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            # Split by Unit Separator
            parts = line.split("\x1f")
            if len(parts) != 5:
                # Fallback if split fails or data is incomplete
                sys.stderr.write(
                    f"Warning: expected 5 fields but got {len(parts)}; skipping line: {line[:50]}...\n"
                )
                continue
            commit_hash = parts[0]
            subject = parts[1]
            author = parts[2]
            date = parts[4]
            category = "other"
            scope = ""
            description = subject
            # Try to match Conventional Commit format
            match = CC_REGEX.match(subject)
            if match:
                commit_type = match.group(1)
                scope = match.group(3) if match.group(3) else ""
                description = match.group(4)
                category = TYPE_MAP.get(commit_type, "other")
            else:
                # Heuristic categorization
                lower_subject = subject.lower()
                for keywords, cat in HEURISTIC_MAP:
                    if any(kw in lower_subject for kw in keywords):
                        category = cat
                        break
            # Output format (Unit Separator \x1f delimited): category\x1fscope\x1fdescription\x1fhash\x1fauthor\x1fdate
            print(f"{category}\x1f{scope}\x1f{description}\x1f{commit_hash}\x1f{author}\x1f{date}")
        except Exception as e:
            # Log error to stderr but don't crash
            sys.stderr.write(f"Error parsing line: {line[:50]}... - {e}\n")


if __name__ == "__main__":
    parse_commits()
