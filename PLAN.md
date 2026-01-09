# Refactoring and Optimization Plan for Revanced-auto

## Goal
Optimize the codebase for performance, maintainability, and reliability by refactoring duplicate code, improving efficiency, fixing errors, updating dependencies, and ensuring dynamic CI/CD workflows.

## Phase 1: Code Quality & Linting
- [x] **Run Shellcheck:** Analyze all `.sh` files using `shellcheck` to identify syntax errors, quoting issues, and potential bugs.
- [x] **Fix Warnings:** Resolve all identified shellcheck warnings (e.g., SC2086 for quoting, SC2155 for export masking return values).
- [x] **Format Code:** Apply consistent formatting using `shfmt` (or standard bash style) to all scripts.

## Phase 2: Refactoring Duplicated & Inefficient Logic
- [x] **TOML Parsing Optimization:** 
    - `toml_get` is called repeatedly inside loops in `build.sh`. 
    - **Action:** Refactor `process_app_config` to read the entire TOML table into a Bash associative array once per app, reducing process spawning/file I/O.
- [x] **Download Logic Consolidation:**
    - `lib/download.sh` contains similar scraping logic for different sites.
    - **Action:** Extract common scraping patterns (e.g., HTML selector extraction) into helper functions to reduce code duplication.
- [x] **Refactor `eval` usage:**
    - `build.sh` uses `eval` to pass arrays.
    - **Action:** Investigate safer alternatives (e.g., passing by reference using `local -n` in Bash 4.3+) to improve security and readability.

## Phase 3: Performance Optimization
- [x] **HTML Parsing:**
    - `htmlq` is invoked frequently.
    - **Action:** Combine selector queries where possible to extract multiple fields in a single pass instead of multiple `htmlq` calls.
- [x] **Dependency Checks:**
    - `check_prerequisites` in `build.sh` is good, but can be optimized to fail fast.

## Phase 4: Dependency Analysis
- [x] **Binary Verification:**
    - Check versions of binaries in `bin/` (`apksigner`, `dexlib2`, `aapt2`, `htmlq`).
    - **Action:** Ensure `htmlq` and `tq` are up-to-date and compatible with the target architecture.
- [x] **Cleanup:**
    - Remove unused variables or functions identified during refactoring.

## Phase 5: CI/CD Optimization (Dynamic Workflows)
- [x] **Dynamic Build Matrix:**
    - The `.github/workflows/build.yml` currently has a hardcoded matrix of apps.
    - **Action:** Create a helper script (e.g., `scripts/generate_matrix.sh`) that parses `config.toml`, filters enabled apps, and outputs a JSON matrix compatible with GitHub Actions.
    - **Action:** Update `.github/workflows/build.yml` to run this script in a setup job and pass the dynamic matrix to the build job.
- [x] **Validation:**
    - Ensure `config.toml` structure is validated before the matrix is generated to prevent CI failures.

## Phase 6: Final Verification
- [x] **Build Test:** Run a dry-run or full build (if possible) to ensure refactoring hasn't broken the build logic.
- [x] **Verify TODOs:** Check if any `TODO` comments in `lib/` were addressed by the refactoring.
