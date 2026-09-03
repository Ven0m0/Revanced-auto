# Changelog

This file is maintained automatically by [release-please](https://github.com/googleapis/release-please) from [Conventional Commits](https://www.conventionalcommits.org/). Entries after `1.0.0` are generated; edit `release-please-config.json` to change section mapping.

## 1.0.0 (2026-09-03)

Initial documented state of the project, backfilled from repository history.

### Added

- Python CLI build pipeline (`python -m scripts.cli`) covering config loading, version resolution, download, patch, sign, and artifact output, with `build.sh` kept as a compatibility wrapper.
- Morphe (`MorpheApp/morphe-cli` + `MorpheApp/morphe-patches`) as the default patcher, with CLI profile auto-detection for ReVanced CLI v5/v6, Morphe, and Adobo.
- Stock APK scrapers for APKMirror, APKMonk, APKPure, Aptoide, Uptodown, and GitHub releases.
- Version tracking to skip unchanged builds (`scripts.cli version-tracker`).
- Auto-discovered plugin hooks (`scripts/plugins/`) with `pre_pipeline` / `post_pipeline` stages.
- APK re-signing via `apksigner.jar` restricted to v1+v2 signature schemes.
- Pytest suite covering config, version tracking, network, APK, and notifier logic.

### Changed

- Removed AAPT2 optimization and the custom-AAPT2-binary CLI flag: the optimize path had no working implementation (`scripts/aapt2-optimize.sh` did not exist) and the custom-binary path added third-party binary risk without a corresponding benefit; the patcher CLI's own bundled aapt2 is used instead.
- Dropped the unused `compression-level` config key.
- Consolidated GitHub Actions workflows from six to three plus release automation: `build.yml` now covers both scheduled/matrix builds and manual single-app dispatch; `ci.yml` merges linting and PR validation; `pages.yml` is unchanged.

### Documentation

- Refreshed `README.md` to match the shipped `config.toml` app sections and Python version requirement.
