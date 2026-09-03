# Changelog

This file is maintained automatically by [release-please](https://github.com/googleapis/release-please) from [Conventional Commits](https://www.conventionalcommits.org/). Entries after `1.0.0` are generated; edit `release-please-config.json` to change section mapping.

## [1.1.0](https://github.com/Ven0m0/Revanced-auto/compare/v1.0.0...v1.1.0) (2026-09-03)


### Added

* add APKMonk source, fix Morphe .mpp update check, add Telegram notifications, add Termux bootstrap ([#119](https://github.com/Ven0m0/Revanced-auto/issues/119)) ([9eb8efd](https://github.com/Ven0m0/Revanced-auto/commit/9eb8efd94ab372c8f5a40fd463c1ba08c828aac4))
* add Python cache CLI support ([#139](https://github.com/Ven0m0/Revanced-auto/issues/139)) ([a7b3086](https://github.com/Ven0m0/Revanced-auto/commit/a7b308660c63d45c5d3420f2d7c116c220f094a3))
* **builder:** implement optional APK processing engine system ([#257](https://github.com/Ven0m0/Revanced-auto/issues/257)) ([76698e6](https://github.com/Ven0m0/Revanced-auto/commit/76698e667646e44b8eeddf94cd7c9b94eeca1f50))
* **builder:** support dynamic artifact name derivation for CLI and patches ([#253](https://github.com/Ven0m0/Revanced-auto/issues/253)) ([f6fb525](https://github.com/Ven0m0/Revanced-auto/commit/f6fb525bd1e0fdfa9cb2cce3f5512d4e0cd79776))
* consolidate all open PR improvements (perf, tests, cleanup) ([179234d](https://github.com/Ven0m0/Revanced-auto/commit/179234d309dcdf429b5a1adb4ee30b4cad4ddc04))
* consolidate PRs [#170](https://github.com/Ven0m0/Revanced-auto/issues/170) [#171](https://github.com/Ven0m0/Revanced-auto/issues/171) [#172](https://github.com/Ven0m0/Revanced-auto/issues/172) [#175](https://github.com/Ven0m0/Revanced-auto/issues/175) with all review suggestions applied ([d60fedf](https://github.com/Ven0m0/Revanced-auto/commit/d60fedfd9c7fe6ce52bcadadacbdce179d418659))
* dynamic aapt2 fetching from GitHub + Morphe/Enhancify integration ([#105](https://github.com/Ven0m0/Revanced-auto/issues/105)) ([69f2dea](https://github.com/Ven0m0/Revanced-auto/commit/69f2dea21982575c2132ca957569b2750a23c0f0))
* enable APK checking in main loop ([#124](https://github.com/Ven0m0/Revanced-auto/issues/124)) ([dc31d49](https://github.com/Ven0m0/Revanced-auto/commit/dc31d494ea88e0ca52d1e80c9b1f661a44405f88))
* **helpers:** improve aapt2 detection with auto-selection ([cea57bc](https://github.com/Ven0m0/Revanced-auto/commit/cea57bc4149db493cf19fbf26acd5919fca4381a))
* Implement APK version check in dependency-checker.sh ([#125](https://github.com/Ven0m0/Revanced-auto/issues/125)) ([3487508](https://github.com/Ven0m0/Revanced-auto/commit/348750870050fc151b3b655f01eaaf3264592d02))
* integrate uni-apks ([#211](https://github.com/Ven0m0/Revanced-auto/issues/211)) ([c554adc](https://github.com/Ven0m0/Revanced-auto/commit/c554adcfb572fad4d020cdade2f20eafbf4756b4))
* Morphe ecosystem integration (CLI profiles, docs) ([#261](https://github.com/Ven0m0/Revanced-auto/issues/261)) ([c61dc38](https://github.com/Ven0m0/Revanced-auto/commit/c61dc38bb2476c7a10cf695190885a30973ecc2a))
* **scripts:** add Python HTML parser to replace htmlq ([7c49e7e](https://github.com/Ven0m0/Revanced-auto/commit/7c49e7e343b1c482130128965970910ab583ff0d))


### Fixed

* **cli:** resolve ModuleNotFoundError when running cli.py directly ([f4a5209](https://github.com/Ven0m0/Revanced-auto/commit/f4a5209af8c15657503fc4ff59739612baaa18fd))
* **gitignore:** Allow tracking of tests directory ([fd902cf](https://github.com/Ven0m0/Revanced-auto/commit/fd902cf1a536cf4cb56b31fc1b99e4c30d673876))
* regenerate uv.lock to resolve types-toml source field ambiguity ([#115](https://github.com/Ven0m0/Revanced-auto/issues/115)) ([cf88321](https://github.com/Ven0m0/Revanced-auto/commit/cf88321c1a05d030d0c434d48185e5fdcda432f9))
* resolve ruff lint errors in Python files and test suite ([#101](https://github.com/Ven0m0/Revanced-auto/issues/101)) ([1eb5a44](https://github.com/Ven0m0/Revanced-auto/commit/1eb5a4477e8767cc3dd7b0dd270485f4ba3631bc))
* resolve workflow YAML issues and Python build loop ([#259](https://github.com/Ven0m0/Revanced-auto/issues/259)) ([d53a846](https://github.com/Ven0m0/Revanced-auto/commit/d53a8466468f2efe39b55d0b678782825f631521))
* **tests:** remove tests for deleted module interfaces after refactor ([f997c08](https://github.com/Ven0m0/Revanced-auto/commit/f997c08737f96ad9dbcb73eea4dfa211e70679bb))
* update GitHub Actions dependencies and add Python dependency man… ([#22](https://github.com/Ven0m0/Revanced-auto/issues/22)) ([5fdb9d1](https://github.com/Ven0m0/Revanced-auto/commit/5fdb9d1d59e16b4af8d5807f3f70a2b2672259a1))


### Changed

* **assets:** Update asset paths in patching.sh ([c79a075](https://github.com/Ven0m0/Revanced-auto/commit/c79a075ac3d0669cda77627e0f62ee8f42f32802))
* **checks:** Centralize environment checks in lib/checks.sh and update build.sh ([9d7b603](https://github.com/Ven0m0/Revanced-auto/commit/9d7b60327910f5c28bba60bc6efda47a7c91a03d))
* **checks:** Refactor check-env.sh to use centralized checks ([85a5b0b](https://github.com/Ven0m0/Revanced-auto/commit/85a5b0b57cd77fd7f120549489a8c7ee9af313d3))
* **config:** Remove deprecated toml_parse_table_to_array function ([6c3c8d1](https://github.com/Ven0m0/Revanced-auto/commit/6c3c8d1b4deba92c37f1281a653bb1ad7cb23694))
* **helpers:** replace htmlq with Python HTML parser ([5006c98](https://github.com/Ven0m0/Revanced-auto/commit/5006c9820cb6b422c1f08d90393ec767411b819c))
* move lib/ utilities to scripts/lib/ ([725400f](https://github.com/Ven0m0/Revanced-auto/commit/725400fd4befc82ee5bee99642de20355654b573))
* optimize APKMonk CSS selectors by removing redundant nested loops ([#126](https://github.com/Ven0m0/Revanced-auto/issues/126)) ([b1c1ab4](https://github.com/Ven0m0/Revanced-auto/commit/b1c1ab4ac870c7726a635e530743ad23565c66ff))
* optimize java args across the project ([a83e1cf](https://github.com/Ven0m0/Revanced-auto/commit/a83e1cf21e3c2ede1106a7a276c0aad99c8e2c7c))
* optimize java args and fix CI syntax error ([12046a2](https://github.com/Ven0m0/Revanced-auto/commit/12046a2fc23747d139aeaf5c5b6eb16f7df73be2))
* purge dead code, fix config contradictions, enhance GitHub Pages site ([0562097](https://github.com/Ven0m0/Revanced-auto/commit/05620976e24742efd68d929b786a38333e3b3f6a))
* Python 3.13+ standards with strict typing, orjson, dataclasses ([#108](https://github.com/Ven0m0/Revanced-auto/issues/108)) ([1d0912a](https://github.com/Ven0m0/Revanced-auto/commit/1d0912a2d98ce8143470321910535b4480cd9bf2))
* remove redundant string stripping in apkmirror_search.py ([#97](https://github.com/Ven0m0/Revanced-auto/issues/97)) ([340eebc](https://github.com/Ven0m0/Revanced-auto/commit/340eebc192e8509652c2a8af22686d96adbab614))
* **structure:** Move assets and test configs to dedicated folders ([d04b50e](https://github.com/Ven0m0/Revanced-auto/commit/d04b50ed93b42e9ef6340569ad6d56083ee4da7d))
* update all imports to reference scripts/lib/ ([a8c5be0](https://github.com/Ven0m0/Revanced-auto/commit/a8c5be073a5155e9dd3b7cbf4ebb6f780df62954))


### Documentation

* add Claude Code automations design doc ([f87b6de](https://github.com/Ven0m0/Revanced-auto/commit/f87b6de9adfdb95f7e8eaeb5cdb32c17b240130f))
* add Claude Code automations implementation plan ([2d358e9](https://github.com/Ven0m0/Revanced-auto/commit/2d358e93a5e5f9143d345bb153ac685fdf0a1387))
* add PRD for refactor phases 3-5 ([43c0050](https://github.com/Ven0m0/Revanced-auto/commit/43c005045a68c3ddc98cf406841c6f432e92570f))
* **architecture:** Update CLAUDE.md with scripts/lib structure ([e26d4c8](https://github.com/Ven0m0/Revanced-auto/commit/e26d4c89c2d1fdf70d76b8f52f6bc9c9b905c62b))
* **developer:** Update all developer documentation for new structure ([a8c16ee](https://github.com/Ven0m0/Revanced-auto/commit/a8c16eee3fc1f1033dd056b5a5c144514e55a6df))
* expand AGENTS.md with comprehensive AI agent guidance ([#93](https://github.com/Ven0m0/Revanced-auto/issues/93)) ([f63f829](https://github.com/Ven0m0/Revanced-auto/commit/f63f82930af6b6714cbeea77f17f3a766b8610d2))
* optimize AGENTS.md and copilot-instructions for AI ([#117](https://github.com/Ven0m0/Revanced-auto/issues/117)) ([26aede9](https://github.com/Ven0m0/Revanced-auto/commit/26aede9ea2911fa145f04f0685a086c050c9a37f))
* optimize and restructure CLAUDE.md for better usability ([#25](https://github.com/Ven0m0/Revanced-auto/issues/25)) ([42be0ae](https://github.com/Ven0m0/Revanced-auto/commit/42be0ae0e569c2b78cdd69400d3877fa1d27c651))
* **plans:** add morphe ecosystem integration plan ([#260](https://github.com/Ven0m0/Revanced-auto/issues/260)) ([cab0c88](https://github.com/Ven0m0/Revanced-auto/commit/cab0c88c6f1d66555044b7773a1a30d9d5e24e37))
* **progress:** Complete Phase 5 documentation enhancement ([bff4488](https://github.com/Ven0m0/Revanced-auto/commit/bff448829fa5db28f62eb5a829e7e40326c14840))
* **python:** Enhance toml_get.py inline documentation ([b6c8b00](https://github.com/Ven0m0/Revanced-auto/commit/b6c8b00153a67f6ab9f411d5799d8dc67e0c0479))
* **readme:** Update prerequisites and architecture ([4b1e059](https://github.com/Ven0m0/Revanced-auto/commit/4b1e05956b718732d7275671d29a00f0b01a445c))
* refactor README ([#143](https://github.com/Ven0m0/Revanced-auto/issues/143)) ([b30e389](https://github.com/Ven0m0/Revanced-auto/commit/b30e389ad3a93058ab44534a10ad15bae8ee86e9))
* **refactor:** extend roadmap with phases 4-5 ([2475be2](https://github.com/Ven0m0/Revanced-auto/commit/2475be28ffbea919c13fcbde59fcbc732bd2cf6d))
* remove deprecated documentation ([73746f1](https://github.com/Ven0m0/Revanced-auto/commit/73746f1fb4de8a44dd79934f147922d158748c85))
* rewrite AGENTS.md and copilot-instructions.md with full codebase context ([#132](https://github.com/Ven0m0/Revanced-auto/issues/132)) ([321189e](https://github.com/Ven0m0/Revanced-auto/commit/321189eedd35e4be14c85d84ecb71e86b74cad16))
* update PLAN.md and TODO.md ([#251](https://github.com/Ven0m0/Revanced-auto/issues/251)) ([d80a448](https://github.com/Ven0m0/Revanced-auto/commit/d80a448f96fe1fd49611404a226da2cee7e51fe1))
* update progress log after Phase 3 completion ([fb8bef7](https://github.com/Ven0m0/Revanced-auto/commit/fb8bef7d06bfb8b7a19613c1356d3b6ed17b5d08))
* update progress log after Phase 4 completion ([eb5a28b](https://github.com/Ven0m0/Revanced-auto/commit/eb5a28ba051b1d68894d7e3f2602f7da9773c1f0))

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
