#!/usr/bin/env python3
import re
import sys

# Regular expression for Conventional Commits
# Format: type(scope): description
CC_REGEX = re.compile(r"^([a-z]+)(\(([^)]+)\))?:\ (.+)$")

# Mapping from commit type to category
TYPE_MAP = {
    "feat": "features",
    "feature": "features",
    "fix": "fixes",
    "bugfix": "fixes",
    "perf": "performance",
    "performance": "performance",
    "refactor": "refactor",
    "style": "refactor",
    "docs": "documentation",
    "doc": "documentation",
    "test": "tests",
    "tests": "tests",
    "build": "build",
    "ci": "build",
    "chore": "build",
    "security": "security",
    "sec": "security",
}

# Heuristic keywords for non-conventional commits
HEURISTIC_MAP = [
    (["add", "implement", "new", "create"], "features"),
    (["fix", "resolve", "correct", "patch"], "fixes"),
    (["update", "upgrade", "bump"], "updates"),
    (["improve", "optimize", "enhance", "better"], "improvements"),
    (["remove", "delete", "deprecate"], "removals"),
    (["security", "vulnerability", "cve"], "security"),
]


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
