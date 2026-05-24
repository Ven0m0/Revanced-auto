# ReVanced-auto Implementation Plan

## Overview
Translate `TODO.md` into a sequenced, execution-ready plan to:
1. Integrate features from Morphe-AutoBuilds, uni-apks, Enhancify, revanced-auto-patcher.
2. Default to Morphe CLI/patches.
3. Add `brosssh/revanced-external-bundles` as a patch source.
4. Add `jkennethcarino/adobo` as an alternative patcher.
5. Refresh the GitHub Pages site under `docs/`.
6. Refresh `README.md`.
7. Fix dependency wiring across `mise.toml`, `pyproject.toml`, and `.github/workflows/*.yml`.

## Assumptions
- Existing CLI profile machinery in `scripts/builder/cli_profiles.py` (already has `MORPHE_CLI`) is the extension point for new patchers.
- `patches-source` / `cli-source` TOML keys in `config.toml` (parsed by `scripts/builder/config.py`) are the canonical knobs; new sources extend these rather than introducing parallel config.
- `scripts/scrapers/` base class is the right place for any new release/bundle fetcher.
- GitHub Pages serves from `/docs/` (Jekyll `_config.yml` present); no Pages deploy workflow exists yet.
- Hardened signing flow (`bin/apksigner.jar`, v1+v2) is invariant and must not regress.
- Python target stays `>=3.13`; mise should match, not advance to 3.14.

## Phase 0 — Baseline & Toolchain Fix (blocks everything)
**Goal:** make local + CI installs reproducible before touching feature code.

Tasks:
- T0.1 Reconcile Python version: `mise.toml` (currently pins 3.14) → align to 3.13 series matching `pyproject.toml` `requires-python = ">=3.13"`.
- T0.2 Audit `mise.toml` tool list (Java temurin-25.0.3, uv, jq, zip) against what `check-env.sh` and `build.sh` actually invoke; add missing, drop unused.
- T0.3 Standardize CI bootstrap in `.github/workflows/*.yml`: `mise install` → `uv sync --locked --all-groups` → `./check-env.sh`. Replace any ad-hoc `setup-python` / `setup-java` steps that bypass mise.
- T0.4 Confirm `pyproject.toml` `[tool.uv]` / dependency groups expose dev tools (ruff, mypy, pytest) used by `scripts/lint.sh`.

Validation:
- `mise install && uv sync --locked --all-groups && ./check-env.sh` green locally.
- `./scripts/lint.sh` green.
- CI dry run on a throwaway branch.

Dependencies: none. Must land first.

## Phase 1 — Patch / CLI Source Extensibility
**Goal:** generalize source resolution so adobo + external-bundles + Morphe defaults slot in without forking the pipeline.

Tasks:
- T1.1 In `scripts/builder/cli_profiles.py`, add a profile entry for adobo (e.g. `ADOBO_CLI`) alongside existing `REVANCED_CLI_V5/V6`, `MORPHE_CLI`. Wire detection (JAR fingerprint / manifest sniff) in the same module.
- T1.2 In `scripts/builder/config.py`, ensure `patches-source` (GlobalConfig ~L47, AppConfig ~L93) accepts the bundle ecosystem: a GitHub repo slug, a release asset URL, or a list mixing both. Document accepted forms in docstring.
- T1.3 Add a "patches bundle" fetcher under `scripts/scrapers/` (new module, e.g. `external_bundles.py`) extending the existing scraper base for `brosssh/revanced-external-bundles`. Reuse `scripts/utils/network.py`; no new HTTP stack.
- T1.4 In `scripts/builder/app_processor.py` (`AppBuildContext` ~L340–387), thread the new fields through so `patches_jars` can contain multiple bundle JARs resolved from one logical source.
- T1.5 In `scripts/builder/patcher.py`, branch on the resolved CLI profile to invoke ReVanced CLI vs Morphe CLI vs adobo. Keep the signing step untouched.

Dependencies: Phase 0.

Validation:
- `uv run python -m pytest tests/test_config.py tests/test_version_tracker.py tests/test_network.py -v`
- `python -m scripts.cli check --config config.toml` resolves a Morphe-, an external-bundles-, and an adobo-configured app without error.
- One end-to-end `python -m scripts.cli build ... --build-mode apk` per profile on a small app.

## Phase 2 — Morphe-by-Default + Cross-Repo Feature Integration
**Goal:** flip default behavior to Morphe and absorb useful patterns from the four referenced repos.

Tasks:
- T2.1 In `config.toml`, promote the existing Morphe samples (lines ~184–221) to active defaults: set top-level `cli-source` / `patches-source` to Morphe; keep ReVanced as opt-in override per-app.
- T2.2 Move the disabled `[YouTube-Morphed]` / `[Music-Morphed]` skeletons into the live app section, gated by an enable flag so users can flip back.
- T2.3 Survey the four referenced repos and document a per-repo intake list before coding:
  - Morphe-AutoBuilds — build matrix + Morphe defaults.
  - uni-apks — multi-arch / multi-variant selection logic; map onto `scripts/scrapers/` and version resolver.
  - Enhancify — patch tweaks; reuse existing `Graywizard888/Custom-Enhancify-aapt2-binary` link (`config.toml` L63).
  - revanced-auto-patcher — automation patterns (workflow scheduling, notifier ergonomics).
- T2.4 Land only the deltas that have a clear home in current modules; skip anything that requires a rewrite.

Dependencies: Phase 1 (needs Morphe path proven).

Validation:
- Fresh `python -m scripts.cli build --config config.toml --build-mode apk` defaults to Morphe outputs.
- Per-app override back to ReVanced still works.
- Pytest suite green: `uv run python -m pytest tests -v`.

## Phase 3 — Docs Site Refresh (`docs/`)
**Goal:** make GitHub Pages reflect the new defaults and patch-source matrix.

Tasks:
- T3.1 Update `docs/index.html`, `docs/generator.html`, `docs/CONFIG.md` to describe Morphe-default, external-bundles, adobo.
- T3.2 Decide whether to keep manual `_config.yml` Jekyll publish (push-to-main from `/docs`) or add a `.github/workflows/pages.yml` using `actions/deploy-pages`. Prefer the workflow for reproducibility; tag it with an explicit release version per repo convention.
- T3.3 Regenerate any embedded config samples so `docs/generator.html` emits valid TOML for the new sources.

Dependencies: Phase 1 + 2 (source names must be stable).

Validation:
- `bash -n` on any new shell; lint clean.
- Local Jekyll preview or workflow dry-run; verify `/docs` renders and links resolve.

## Phase 4 — README Refresh
**Goal:** ground-truth the README against the new behavior.

Tasks:
- T4.1 Update `README.md` sections: Requirements, Quick Start, Configuration, Signing & Build Flow.
- T4.2 Add a short "Patch sources" subsection covering Morphe (default), ReVanced, external-bundles, adobo.
- T4.3 Confirm command examples match `scripts/cli.py` surface and `build.sh` wrapper.

Dependencies: Phases 1–3 (so commands and config keys are final).

Validation: manual readthrough; copy-paste each command into a clean shell.

## Cross-Cutting Validation Matrix
- Config/args/version: `uv run python -m pytest tests/test_config.py tests/test_version_tracker.py -v`
- Network/scrapers: `uv run python -m pytest tests/test_network.py -v`
- APK/signing: `uv run python -m pytest tests/test_apk.py -v`
- Full: `uv run python -m pytest tests -v`
- Lint: `./scripts/lint.sh`
- Shell: `bash -n` on any changed `.sh`.

## Open Questions / Blockers
1. **adobo interface**: is `jkennethcarino/adobo` a drop-in CLI invocable like ReVanced CLI, or does it require a different invocation contract? Confirm before T1.5.
2. **external-bundles layout**: are bundles published as GitHub Releases assets, or as repo files? Determines whether T1.3 reuses the release-asset path or needs a raw-content fetcher.
3. **Default flip risk**: switching the global default to Morphe changes outputs for every existing user/config. Confirm this is intended vs. opt-in.
4. **Mise Java pin**: `temurin-25.0.3` vs. CLAUDE.md's "Java 21+" claim — confirm 25 is intentional.
5. **Pages deploy**: keep implicit Jekyll-from-`/docs` or add an explicit `pages.yml` workflow? T3.2 picks the second by default; flag if user prefers the first.
6. **Scope of "integrate features"**: TODO.md lists four repos but not which specific features. T2.3 is the gate; surface an explicit feature list before implementing.

## File Touch Map (reference)
- Toolchain: `mise.toml`, `pyproject.toml`, `.github/workflows/*.yml`, `check-env.sh`
- Sources/patcher: `scripts/builder/cli_profiles.py`, `scripts/builder/config.py`, `scripts/builder/app_processor.py`, `scripts/builder/patcher.py`, new `scripts/scrapers/external_bundles.py`
- Config: `config.toml`
- Docs: `docs/index.html`, `docs/generator.html`, `docs/CONFIG.md`, `docs/_config.yml`, possibly new `.github/workflows/pages.yml`
- README: `README.md`
- Tests: extend `tests/test_config.py`, `tests/test_network.py` as new behavior lands.

## TODO.md → Phase Coverage
- Item 1 (integrate 4 repos) → Phase 2 (T2.3, T2.4)
- Item 2 (Morphe by default) → Phase 2 (T2.1, T2.2)
- Item 3 (external-bundles) → Phase 1 (T1.2, T1.3)
- Item 4 (adobo) → Phase 1 (T1.1, T1.5)
- Item 5 (Pages site) → Phase 3
- Item 6 (README) → Phase 4
- Item 7 (mise/uv/workflows) → Phase 0
