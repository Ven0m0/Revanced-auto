# Phase 2: Reference-repo survey

Quick survey of the four reference repos listed in `TODO.md` to identify
clear-home deltas. Most distinguishing features are already covered by
ReVanced-auto; what follows is the net delta after that comparison.

## RookieEnough/Morphe-AutoBuilds

Matrix-build automation on GitHub Actions, daily scheduled builds, multi-arch per app.

| Feature | Status in this repo |
| --- | --- |
| Multi-arch per app | `arch = "arm64-v8a"`, `"arm-v7a"`, `"both"`, `"all"` (per app) |
| Multi-source failover | `apkmirror-dlurl`, `apkpure-dlurl`, `uptodown-dlurl`, `aptoide-dlurl`, `archive-dlurl`, `apkmonk-dlurl`; `AppProcessor._determine_download_source` resolves them |
| Granular patch lists | `excluded-patches`, `included-patches`, `exclusive-patches` |
| Daily build schedule | `.github/workflows/build.yml` (cron already in place) |
| Per-app arch list | Implemented via per-app `arch` override |

**Net delta:** None. Already covered.

## krvstek/uni-apks

Multi-arch / universal builds with a single config.

| Feature | Status in this repo |
| --- | --- |
| `arch = "both"` for arm64+armv7 | `Architecture.BOTH` in `app_processor.py:32-57` |
| `arch = "all"` (universal) | `Architecture.ALL` |
| Auto CLI selection | `cli_profile = "auto"` in `GlobalConfig` (Phase 1 fix routes all CLI paths through the profile system) |

**Net delta:** None. Already covered.

## Graywizard888/Enhancify

Custom aapt2 binary integration and APK tweaks.

| Feature | Status in this repo |
| --- | --- |
| `aapt2-source` | `scripts/builder/config.py` already accepts aapt2 options |
| `use-custom-aapt2` | Config flag already wired |
| APK tweaks (media optimizer, APK optimizer, etc.) | All 7 engines from the apk-tweak project are integrated (see `scripts/builder/engines/`) |

**Net delta:** None. Already covered.

## Sp3EdeR/revanced-auto-patcher

Automation patterns, CI/CD workflows.

| Feature | Status in this repo |
| --- | --- |
| Patcher automation | Python pipeline via `python -m scripts.cli` |
| GitHub Actions | `.github/workflows/build.yml`, `pages.yml`, others |
| Version tracking | `version_tracker.py` + `last_built_versions.json` |
| Notification hooks | Notifier system already in place |

**Net delta:** None actionable without major refactor.

## Conclusion

No clear-home deltas surfaced that are not already implemented. The CLI
profile fix (Phase 1) was the actual blocker for Morphe/Adobo/external
bundles interoperability. Closing Phase 2 with no further code changes.
