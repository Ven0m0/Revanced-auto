# Specification: Refactor Codebase & Clean Up Repo

## 1. Overview
This track focuses on improving the maintainability and structural organization of the ReVanced Builder project. It involves consolidating duplicate logic, organizing project root assets, removing deprecated code, and improving the resilience of the build tools (specifically `aapt2`) on different architectures.

## 2. Objectives
-   **Centralize Logic:** Eliminate code duplication by moving environment checks to a shared library.
-   **Organize Structure:** Declutter the root directory by moving static assets (`ks.keystore`, `sig.txt`) and test configurations to dedicated subdirectories.
-   **Fix Dependencies:** Remove reliance on brittle emulation hacks for `x86_64` systems and prioritize system-installed tools.
-   **Cleanup:** Remove deprecated and unsafe functions.

## 3. Scope
### 3.1 Refactoring
-   **Files:** `build.sh`, `check-env.sh`, `lib/config.sh`, `lib/helpers.sh`, `lib/patching.sh`.
-   **New Files:** `lib/checks.sh` (for centralized checks).

### 3.2 Organization
-   **New Directories:** `assets/`, `tests/`.
-   **Moves:**
    -   `ks.keystore` -> `assets/ks.keystore`
    -   `sig.txt` -> `assets/sig.txt`
    -   `config-*-test.toml` -> `tests/`

### 3.3 Dependency Management
-   **Tool:** `aapt2`
-   **Logic:** Update detection to prefer `command -v aapt2` before falling back to bundled binaries. Remove the `x86_64 -> arm64` forced mapping unless absolutely necessary and properly handled.

## 4. Acceptance Criteria
-   [ ] `./check-env.sh` runs successfully and correctly identifies tools.
-   [ ] `./build.sh` runs successfully and locates assets in their new `assets/` location.
-   [ ] The root directory is free of `ks.keystore`, `sig.txt`, and test configs.
-   [ ] `lib/config.sh` no longer contains `toml_parse_table_to_array`.
-   [ ] On an x86_64 system, the build attempts to use a system `aapt2` if available, or fails with a clear message if no compatible binary is found (instead of silently using an incompatible ARM binary).
