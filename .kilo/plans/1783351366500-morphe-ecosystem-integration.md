# Implementation Plan

> **Status**: Updated 2026-07-06  
> **Purpose**: Handoff-ready implementation plan for Morphe ecosystem integration  
> **Source**: Derived from TODO.md + codebase inspection

---

## Executive Summary

This plan integrates the Morphe patcher ecosystem as the default, adds support for multiple patch sources (Adobo, external-bundles, etc.), and refreshes documentation. Many foundational tasks are already complete; remaining work focuses on bug fixes, feature integration from 4 reference repos, and documentation updates.

---

## Completed Work (No Action Required)

The following items from the original PLAN.md are already implemented:

| Task | Status | Evidence |
|------|--------|----------|
| T1.1 ADOBO_CLI profile | ✅ Done | `scripts/builder/cli_profiles.py:269-274` |
| T1.2 patches_source/cli_source config | ✅ Done | `scripts/builder/config.py:47-48,103-104` |
| T1.3 external_bundles.py scraper | ✅ Done | `scripts/scrapers/external_bundles.py` (full GraphQL client) |
| T2.1 Morphe as default | ✅ Done | `config.toml:42-43` |
| T2.2 YouTube-Morphed/Music-Morphed | ✅ Done | `config.toml:203-212,249-258` (enabled=true) |
| T3.2 Pages workflow | ✅ Done | `.github/workflows/pages.yml` (Jekyll from /docs) |
| T4.1 README patch sources section | ✅ Done | `README.md:108-119` |

---

## Phase 1: Critical Bug Fix — CLI Profile Integration

### Problem
`_run_patcher()` in `scripts/builder/app_processor.py:998-1031` uses **hardcoded ReVanced CLI v6 flags** (`-i`, `-o`, `-e`, `-d`, `-k`) instead of the detected CLI profile's argument mappings. This breaks Morphe CLI, Adobo CLI, and ReVanced CLI v5.

### Solution
Refactor `_run_patcher()` to use `cli_profile.build_patch_args()` from `cli_profiles.py`.

### Implementation Steps

**T1.1 Detect CLI profile at build time**
- File: `scripts/builder/app_processor.py`
- Location: `_run_patcher()` method (line 969+)
- Action: Before building patch args, detect the CLI profile:
  ```python
  from scripts.builder.cli_profiles import detect_cli_profile, PatchCommandConfig
  
  cli_profile = detect_cli_profile(context.cli_jar)
  ```

**T1.2 Build patch args via profile**
- Replace hardcoded arg construction (lines 998-1021) with:
  ```python
  config = PatchCommandConfig(
      apk_path=stock_apk,
      output_path=context.output_path,
      patches_jars=context.patches_jars,
      exclude=context.excluded_patches if not context.exclusive_patches else [],
      include=context.included_patches if context.exclusive_patches else [],
      keystore=keystore,
      rip_lib=list(context.riplib) if context.riplib else [],
  )
  patch_args = cli_profile.build_patch_args(config)
  ```

**T1.3 Handle riplib edge case**
- Current code checks `--rip-lib` support via `patch --help` (line 1033-1059)
- This logic should be preserved but integrated with the profile system
- If profile doesn't support RIP_LIB mapping, skip it

**T1.4 Validate with tests**
- Add unit tests for each CLI profile's `build_patch_args()` output
- Test e2e build with Morphe CLI, ReVanced CLI v5, v6, and Adobo
- Verify: `pytest tests/test_config.py tests/test_engines.py -v`

### Validation
```bash
# Unit tests
uv run python -m pytest tests/test_config.py -v

# Manual e2e test per profile
uv run python -m scripts.cli build --config config.toml --build-mode apk --parallel 1
# Verify Morphe, ReVanced v5/v6, and Adobo all produce valid patched APKs
```

---

## Phase 2: Feature Integration from Reference Repos

### Context
TODO.md specifies integrating features from 4 repositories:
1. `RookieEnough/Morphe-AutoBuilds` — matrix builds
2. `krvstek/uni-apks` — multi-arch support
3. `Graywizard888/Enhancify` — APK tweaks
4. `Sp3EdeR/revanced-auto-patcher` — automation patterns

### Approach
Survey each repo, identify **clear-home deltas** (features that fit current architecture without major rewrites), and implement only those.

### Implementation Steps

**T2.1 Survey Morphe-AutoBuilds**
- Repo: https://github.com/RookieEnough/Morphe-AutoBuilds
- Focus: Matrix build strategies, version resolution patterns
- Deliverable: List of features to adopt (e.g., parallel version checks, fallback logic)

**T2.2 Survey uni-apks**
- Repo: https://github.com/krvstek/uni-apks
- Focus: Multi-arch build support, APK variant selection
- Deliverable: Identify if current `arch` config needs enhancement (e.g., `both` for arm64+arm-v7a)

**T2.3 Survey Enhancify**
- Repo: https://github.com/Graywizard888/Enhancify
- Focus: Custom aapt2 binary integration (already partially done: `config.toml:70`)
- Deliverable: Verify `aapt2-source` and `use-custom-aapt2` are wired correctly

**T2.4 Survey revanced-auto-patcher**
- Repo: https://github.com/Sp3EdeR/revanced-auto-patcher
- Focus: Automation patterns, CI/CD workflows
- Deliverable: Identify workflow improvements for `.github/workflows/build.yml`

**T2.5 Implement feature deltas**
- Based on survey results, implement only features that:
  - Fit current module structure
  - Don't require major refactoring
  - Provide clear user value
- Document each adopted feature in README.md

### Validation
- Each implemented feature must pass `pytest tests -v`
- E2e build with new features enabled

---

## Phase 3: builder-for-morphe Integration

### Context
TODO.md specifies implementing features from `nvbangg/builder-for-morphe`.

### Current State
- builder-for-morphe is a **complete Python rewrite** based on j-hc/uni-apks
- It uses the same config.toml format as this repo
- Key features: auto-updates via Obtainium, pre-configured app support, automatic upstream sync

### Integration Strategy
Since this repo already has similar functionality, focus on:
1. **Feature parity check**: Ensure all builder-for-morphe features are present
2. **Config compatibility**: Verify config.toml format matches
3. **Documentation**: Reference builder-for-morphe as a template/fork option

### Implementation Steps

**T3.1 Feature parity audit**
- Compare builder-for-morphe's `main.py` and `config.toml` with this repo
- Identify missing features (if any)
- Deliverable: Gap analysis document

**T3.2 Config format alignment**
- Verify this repo's config.toml is compatible with builder-for-morphe's schema
- Add any missing fields if needed
- Ensure backward compatibility

**T3.3 Documentation cross-reference**
- Add section to README.md: "Related Projects" or "Template Forks"
- Link to builder-for-morphe as a simplified alternative
- Example:
  ```markdown
  ## Related Projects
  
  - [builder-for-morphe](https://github.com/nvbangg/builder-for-morphe) — Simplified template fork for building Morphe-patched APKs with minimal setup.
  ```

### Validation
- Config compatibility test: Load builder-for-morphe's config.toml with this repo's parser
- Verify no breaking changes

---

## Phase 4: awesome-for-morphe Documentation

### Context
TODO.md specifies adding info from `nvbangg/awesome-for-morphe` to README and docs, with focus on **installation/setup guide**.

### Current State
- awesome-for-morphe is a curated list of Morphe resources, projects, and patch indexes
- It provides links to official tools, documentation, and community resources
- This repo's README already has a "Patch sources" section but lacks setup guidance

### Implementation Steps

**T4.1 Add Morphe setup guide to README**
- Location: After "Quick start" section
- Content:
  ```markdown
  ## Morphe Setup Guide
  
  This repo uses **Morphe** as the default patcher (MorpheApp/morphe-patches + MorpheApp/morphe-cli).
  
  ### Prerequisites
  - Java 21+ (for Morphe CLI)
  - Python 3.13+ (for build scripts)
  - `uv` for dependency management
  
  ### Quick Setup
  1. Clone this repo: `git clone <repo-url>`
  2. Install dependencies: `mise install && uv sync --locked --all-groups`
  3. Verify environment: `bash ./check-env.sh`
  4. Configure apps in `config.toml` (YouTube-Morphed and Music-Morphed are enabled by default)
  5. Build: `uv run python -m scripts.cli build --config config.toml`
  
  ### Morphe Resources
  - [Official Morphe Website](https://morphe.software)
  - [Morphe Patches](https://morphe-patches.software)
  - [Morphe Documentation](https://github.com/MorpheApp/morphe-documentation)
  - [Awesome for Morphe](https://github.com/nvbangg/awesome-for-morphe) — Curated list of all Morphe resources
  - [Patch Explorer](https://patch-explorer.web.app/) — Browse all supported apps and patches
  ```

**T4.2 Update docs/CONFIG.md**
- Add Morphe-specific configuration examples
- Document `cli-profile = "auto"` behavior
- Add troubleshooting section for Morphe CLI detection

**T4.3 Add patch index links to docs**
- Create `docs/PATCHES.md` or update `docs/README.md`
- List all patch indexes from awesome-for-morphe:
  - Official Website
  - Awesome for Morphe Website
  - Patch Explorer
  - Revanced External Bundles
  - Community Patch Space Explorer
  - Morphe Patch Tracker

### Validation
- Verify all links resolve
- Copy-paste setup commands into clean shell
- Jekyll preview renders correctly

---

## Phase 5: Documentation Refresh

### Context
Update GitHub Pages website and config generator for new features.

### Implementation Steps

**T5.1 Update docs/index.html**
- Add Morphe/Adobo/external-bundles to patch sources list
- Update config examples

**T5.2 Update docs/generator.html**
- Add new config options to generator:
  - `cli-profile`
  - `aapt2-source`
  - `use-custom-aapt2`
  - Engine toggles (`enable-media-optimizer`, etc.)
- Regenerate sample configs

**T5.3 Verify docs deployment**
- Check `.github/workflows/pages.yml` triggers on docs/** changes
- Verify Jekyll build succeeds locally: `cd docs && jekyll build`

### Validation
- GitHub Pages preview renders
- Config generator produces valid TOML
- All links resolve

---

## Phase 6: README Final Refresh

### Context
Verify README command examples match actual CLI and document all new features.

### Implementation Steps

**T6.1 Verify command examples**
- Test all commands in README.md against `scripts/cli.py`
- Ensure `build.sh` wrapper examples still work
- Update any outdated flags or options

**T6.2 Document engine system**
- README already has "Optional APK-tweak engines" section (line 128+)
- Verify it's complete and accurate
- Add examples for each engine

**T6.3 Add "Related Projects" section**
- Link to builder-for-morphe
- Link to awesome-for-morphe
- Link to other Morphe ecosystem tools

### Validation
- Copy-paste all README commands into clean shell
- Verify each command works as documented

---

## Open Questions (Handoff Items)

The following questions require user input or further investigation:

1. **Java version pin**: Is Java 25 intentional? (Current: `mise.toml` may pin Java 25, but README says 21+)
   - **Recommendation**: Align with README (Java 21+) unless there's a specific reason for 25

2. **Feature scope from 4 repos**: Which specific features from Morphe-AutoBuilds, uni-apks, Enhancify, and revanced-auto-patcher should be implemented?
   - **Recommendation**: Survey first (Phase 2), then prioritize based on user value

3. **builder-for-morphe integration depth**: Should this repo:
   - (a) Remain independent with cross-references, or
   - (b) Adopt builder-for-morphe's config schema entirely, or
   - (c) Merge codebases?
   - **Recommendation**: Option (a) — remain independent, add cross-references

4. **External-bundles default**: Should `brosssh/revanced-external-bundles` be a default patches-source option, or opt-in only?
   - **Recommendation**: Opt-in only (current behavior)

---

## Validation Matrix

| Change Type | Validation Command |
|-------------|-------------------|
| Config changes | `uv run python -m pytest tests/test_config.py tests/test_version_tracker.py -v` |
| Network/scraper changes | `uv run python -m pytest tests/test_network.py -v` |
| APK/signing changes | `uv run python -m pytest tests/test_apk.py -v` |
| Engine changes | `uv run python -m pytest tests/test_engines.py -v` |
| CLI profile changes | `uv run python -m pytest tests/test_config.py -v` + manual e2e build per profile |
| Documentation changes | Verify links resolve, Jekyll preview renders |
| Full test suite | `uv run python -m pytest tests -v` |
| Lint | `./scripts/lint.sh` |
| Shell scripts | `bash -n <changed.sh>` |

---

## Implementation Order

1. **Phase 1** (Critical) — Fix CLI profile bug in `_run_patcher()`
2. **Phase 4** (High) — Add awesome-for-morphe setup guide to README
3. **Phase 2** (Medium) — Survey and implement feature deltas from 4 repos
4. **Phase 3** (Medium) — builder-for-morphe integration/audit
5. **Phase 5** (Low) — Docs refresh
6. **Phase 6** (Low) — README final refresh

---

## Success Criteria

- [ ] All CLI profiles (Morphe, ReVanced v5/v6, Adobo) produce valid patched APKs
- [ ] README includes Morphe setup guide with working commands
- [ ] docs/CONFIG.md documents all new config options
- [ ] GitHub Pages renders correctly
- [ ] All pytest tests pass
- [ ] Lint passes with no errors
- [ ] No breaking changes to existing config.toml format

---

## Notes for Implementer

- **Phase 1 is blocking** — the CLI profile bug will cause builds to fail with non-ReVanced-v6 CLIs
- **Phase 2 requires research** — survey the 4 repos before implementing anything
- **Phase 3 is low-risk** — mostly documentation and config compatibility checks
- **Phase 4-6 are documentation** — can be done in parallel or deferred
- **Test frequently** — run `pytest tests -v` after each phase
- **Keep changes minimal** — avoid broad refactors unless explicitly requested
