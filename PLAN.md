# Implementation Plan

## Phase 0: Toolchain Fix
- T0.1 Align `mise.toml` Python to 3.13 (match `pyproject.toml`)
- T0.2 Audit `mise.toml` tools vs `check-env.sh`/`build.sh`; add missing or drop unused
- T0.3 Standardize CI: `mise install` → `uv sync --locked --all-groups` → `./check-env.sh`
- T0.4 Verify dev tools (ruff/mypy/pytest) in `pyproject.toml` groups

**Validate:** `mise install && uv sync --locked --all-groups && ./check-env.sh && ./scripts/lint.sh`

## Phase 1: Patch/CLI Extensibility
- T1.1 Add `ADOBO_CLI` profile in `scripts/builder/cli_profiles.py` with detection
- T1.2 Add `cli_source` to GlobalConfig/AppConfig; `patches-source` accepts repo slug, release URL, or list
- T1.3 Create `scripts/scrapers/external_bundles.py` for `brosssh/revanced-external-bundles`
- T1.4 Fix `cli_source`→`patches_source` bug in `scripts/builder/app_processor.py:624`; support multiple bundle JARs
- T1.5 Refactor `ReVancedPatcher` to use `cli_profile.build_patch_args()` instead of hardcoded method

**Validate:** `pytest tests/test_config.py tests/test_version_tracker.py tests/test_network.py -v`; e2e build per profile

## Phase 2: Morphe Default + Feature Integration
- T2.1 Set Morphe as default `cli-source`/`patches-source` in `config.toml`; ReVanced as per-app override
- T2.2 Enable `[YouTube-Morphed]`/`[Music-Morphed]` with enable flag
- T2.3 Survey repos: Morphe-AutoBuilds (matrix), uni-apks (multi-arch), Enhancify (tweaks), revanced-auto-patcher (automation)
- T2.4 Implement only clear-home deltas; skip rewrites

**Validate:** Default build uses Morphe; per-app ReVanced override works; full pytest green

## Phase 3: Docs Refresh
- T3.1 Update `docs/index.html`, `docs/generator.html`, `docs/CONFIG.md` for Morphe/external-bundles/adobo
- T3.2 Add `.github/workflows/pages.yml` with `actions/deploy-pages`
- T3.3 Regenerate config samples in `docs/generator.html`

**Validate:** Jekyll preview renders; links resolve

## Phase 4: README Refresh
- T4.1 Update Requirements, Quick Start, Configuration, Signing & Build Flow
- T4.2 Add "Patch sources" subsection (Morphe default, ReVanced, external-bundles, adobo)
- T4.3 Verify command examples match `scripts/cli.py` and `build.sh`

**Validate:** Copy-paste commands into clean shell

## Phase 5: builder-for-morphe Integration
- T5.1 Research `nvbangg/builder-for-morphe` features and architecture
- T5.2 Identify integration points with existing Morphe CLI profile
- T5.3 Implement feature deltas that fit current module structure
- T5.4 Document new capabilities in README and docs

**Validate:** End-to-end build with builder-for-morphe features; pytest green

## Open Questions
1. `adobo` invocation contract (drop-in or different?)
2. `external-bundles` layout (releases vs repo files?)
3. Morphe default flip intended vs opt-in?
4. Java 25 pin intentional?
5. Pages deploy: workflow vs Jekyll-from-`/docs`?
6. Specific features from 4 repos (T2.3 gate)?

## Validation Matrix
- Config: `pytest tests/test_config.py tests/test_version_tracker.py -v`
- Network: `pytest tests/test_network.py -v`
- APK: `pytest tests/test_apk.py -v`
- Full: `pytest tests -v`
- Lint: `./scripts/lint.sh`
- Shell: `bash -n <changed.sh>`
