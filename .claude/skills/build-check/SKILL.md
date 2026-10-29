---
name: build-check
description: Run lint and the pytest targets that match the files changed in the working tree
disable-model-invocation: true
---

1. List changed files: `git diff --name-only HEAD` (plus untracked via `git status --short`).
2. Pick pytest targets from the CLAUDE.md validation matrix:
   - config, args, version tracking: `tests/test_config.py tests/test_version_tracker.py`
   - network or scrapers: `tests/test_network.py tests/scrapers`
   - APK or signing: `tests/test_apk.py tests/test_keystore.py`
   - anything broader or unclear: `tests`
3. Run `uv run python -m scripts.cli lint`, then `uv run python -m pytest <targets> -v`.
4. Report which checks ran, which failed (with output), and which were skipped. Do not claim success without the test output.
