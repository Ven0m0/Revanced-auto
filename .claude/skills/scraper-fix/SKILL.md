---
name: scraper-fix
description: Checklist for fixing a broken APK scraper (apkmirror, uptodown, apkpure, aptoide, apkmonk) after a site change
---

1. Reproduce: fetch the failing page (Playwright MCP if it needs JS or a challenge) and save the HTML as a fixture under `tests/scrapers/`.
2. Add a failing test in the matching `tests/scrapers/test_<source>.py` against that fixture.
3. Fix the selector or parsing in `scripts/scrapers/<source>.py`. Use `selectolax` and the helpers in `scripts/utils/network.py`; no new HTTP stack.
4. Run `uv run python -m pytest tests/scrapers tests/test_network.py -v`, then `uv run python -m scripts.cli lint`.
5. Do not touch `.github/last_built_versions.json`.
