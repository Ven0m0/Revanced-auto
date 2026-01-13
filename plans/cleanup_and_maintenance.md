# Implementation Plan - Repo Cleanup and Maintenance

## 1. 🔍 Analysis & Context
*   **Objective:** Refactor the codebase to improve maintainability, reduce duplication, organize file structure, and fix the reliance on ARM emulation for x86_64 systems.
*   **Affected Files:**
    -   `build.sh`
    -   `check-env.sh`
    -   `lib/config.sh`
    -   `lib/helpers.sh`
    -   `lib/patching.sh`
    -   `README.md`
    -   `ks.keystore`, `sig.txt` (moved)
    -   `config-*-test.toml` (moved)
*   **Key Dependencies:** `bash`, `java`, `python3` (for TOML), `jq`.
*   **Risks/Unknowns:**
    -   Moving `ks.keystore` and `sig.txt` might break users' existing local setups if they pull changes without reading the changelog. Backward compatibility checks will be added.
    -   Removing the x86_64->arm64 emulation hack for `aapt2` might break builds for x86 users who relied on QEMU, but it fixes the "error" of relying on emulation. We will prioritize system `aapt2` to mitigate this.

## 2. 📋 Checklist
- [ ] Step 1: Centralize Environment Checks (`lib/checks.sh`)
- [ ] Step 2: Refactor `build.sh` and `check-env.sh` to use `lib/checks.sh`
- [ ] Step 3: Remove Deprecated Code from `lib/config.sh`
- [ ] Step 4: Organize Root Directory (Assets & Tests)
- [ ] Step 5: Update `lib/patching.sh` to reference new asset paths
- [ ] Step 6: Improve `aapt2` Detection in `lib/helpers.sh`
- [ ] Step 7: Verification

## 3. 📝 Step-by-Step Implementation Details

### Step 1: Centralize Environment Checks
*   **Goal:** Eliminate code duplication between `build.sh` and `check-env.sh`.
*   **Action:**
    *   Create `lib/checks.sh`.
    *   Extract `check_prerequisites` function from `build.sh` into `lib/checks.sh`.
    *   Incorporate the detailed checks from `check-env.sh` into this single source of truth.

### Step 2: Refactor `build.sh` and `check-env.sh`
*   **Goal:** Use the new shared library.
*   **Action:**
    *   Modify `build.sh`: Source `lib/checks.sh` and remove the inline `check_prerequisites` function.
    *   Modify `check-env.sh`: Simplify it to just source `lib/checks.sh` and run the check function.

### Step 3: Remove Deprecated Code
*   **Goal:** Clean up `lib/config.sh`.
*   **Action:**
    *   Remove `toml_parse_table_to_array` function which is marked as deprecated and unsafe.

### Step 4: Organize Root Directory
*   **Goal:** Reduce clutter in the root directory.
*   **Action:**
    *   Create directory `assets/`.
    *   Create directory `tests/`.
    *   Move `ks.keystore` and `sig.txt` to `assets/`.
    *   Move `config-multi-source-test.toml` and `config-single-source-test.toml` to `tests/`.

### Step 5: Update `lib/patching.sh`
*   **Goal:** Ensure build process finds the moved assets.
*   **Action:**
    *   Update `check_sig` function to look for `assets/sig.txt`.
    *   Update `patch_apk` function to look for `assets/ks.keystore`.
    *   Add fallback logic: Check `assets/` first, if missing check root (and warn/move), if missing fail/create.

### Step 6: Improve `aapt2` Detection
*   **Goal:** Fix the brittle reliance on ARM emulation for x86_64.
*   **Action:**
    *   Modify `set_prebuilts` in `lib/helpers.sh`.
    *   Logic change:
        1. Check if `aapt2` is available in system PATH.
        2. If not, check `bin/aapt2/aapt2-$(uname -m)`.
        3. Remove the block that forces `arch=arm64` when `uname -m` is `x86_64`.
        4. Error out cleanly if no valid `aapt2` is found.

## 4. 🧪 Testing Strategy
*   **Unit Tests:** None (Bash scripts).
*   **Integration Tests:**
    *   Run `./check-env.sh` to verify it correctly identifies installed tools and missing assets.
    *   Run `./build.sh` (dry run or simple build) to ensure it can load config and find assets in `assets/`.
*   **Manual Verification:**
    *   Verify `bin/` still contains necessary jars.
    *   Verify `assets/` contains keystore and sig file.
    *   Verify `tests/` contains test configs.

## 5. ✅ Success Criteria
*   Root directory is cleaner (fewer files).
*   `check-env.sh` and `build.sh` rely on the same code for checks.
*   Deprecated code is removed.
*   x86_64 systems attempt to use system `aapt2` instead of failing or using emulation blindly.
