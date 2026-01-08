# Refactoring and Bug Fixes - January 2025

## Summary

This document describes the refactoring work and bug fixes applied to the ReVanced Builder codebase to ensure APKs build correctly.

## Bug Fixes

### 1. Fixed undefined variable in config.sh (Line 204)
**Issue**: Variable `$ver` was used but undefined, should be `$PATCHES_VER`
**Fix**: Changed `gh_req "$rv_rel/tags/${ver}" -` to `gh_req "$rv_rel/tags/${PATCHES_VER}" -`
**Impact**: Prevents errors when fetching specific patch versions

### 2. Fixed indentation issues in patching.sh (Lines 349-381)
**Issue**: Inconsistent indentation using spaces instead of tabs
**Fix**: Standardized all indentation to tabs for consistency
**Impact**: Improves code readability and prevents potential parsing issues

### 3. Added DEF_ARCH global variable
**Issue**: Architecture default was hardcoded as "all" instead of using config default
**Fix**: Added `DEF_ARCH=$(toml_get "$main_config_t" arch) || DEF_ARCH="arm64-v8a"`
**Impact**: Architecture default now respects config.toml settings

### 4. Added DEF_RIPLIB global variable
**Issue**: Riplib default wasn't properly exposed to build process
**Fix**: Added `DEF_RIPLIB=$(toml_get "$main_config_t" riplib) || DEF_RIPLIB="true"`
**Impact**: Riplib setting now properly propagates from global config to app builds

### 5. Improved riplib handling logic (build.sh Lines 250-259)
**Issue**: Riplib override logic was incomplete and didn't properly handle app-specific settings
**Fix**: Rewrote to properly check app-specific config with fallback to global default
**Impact**: Riplib settings now work correctly per-app with proper warnings

### 6. Enhanced patch_apk error handling (patching.sh Lines 89-100)
**Issue**: Function didn't properly verify output APK exists after successful patching
**Fix**: Added explicit check for output file existence with better error messages
**Impact**: Catches cases where patching succeeds but no output is produced

### 7. Fixed dl_archive function (download.sh Line 274)
**Issue**: Architecture variable had incorrect spacing `${arch// /}` which should be `${arch}`
**Fix**: Changed `grep "${version_f#v}-${arch// /}"` to `grep "${version_f#v}-${arch}"`
**Impact**: Archive.org downloads will now correctly match architecture

### 8. Fixed x86_64 architecture handling (helpers.sh Lines 170-176)
**Issue**: x86_64 systems couldn't find appropriate binaries (only arm/arm64 provided)
**Fix**: Added logic to map x86_64 to arm64 with warning about ARM emulation requirement
**Impact**: x86_64 systems can now build APKs using arm64 binaries (requires ARM emulation)

### 9. Fixed counter increment in check-env.sh (Lines 22, 27, 32)
**Issue**: Counter variables used arithmetic operators that required `(( ))` which caused issues
**Fix**: Changed to standard arithmetic expansion `$((PASS + 1))` for better compatibility
**Impact**: Environment check script now correctly counts passes/fails/warnings

### 10. Fixed environment check for x86_64 architecture (Lines 127-173)
**Issue**: Check failed for x86_64 because no x86_64 binaries exist in bin/aapt2/ and bin/htmlq/
**Fix**: Added special handling for x86_64 to accept arm64 binaries since helpers.sh maps them
**Impact**: Environment check now correctly identifies valid setup on x86_64 systems

### 11. Updated function documentation
**Issue**: Function comments didn't accurately reflect current behavior
**Fix**: Updated documentation for `_apply_riplib_optimization` to indicate it uses global patcher_args
**Impact**: Improves code maintainability

## Code Quality Improvements

### 1. Consistent Tab Indentation
- Standardized all bash files to use tabs for indentation
- Improves consistency and reduces potential parsing issues

### 2. Better Error Messages
- Added more descriptive error messages throughout the codebase
- Makes debugging easier for users

### 3. Improved Variable Naming
- Made global variable names more consistent (DEF_ prefix for defaults)
- Clearer distinction between global defaults and app-specific values

## Testing

All shell scripts pass syntax validation:
```bash
for f in *.sh lib/*.sh scripts/*.sh; do bash -n "$f"; done
```

Environment check script validates all prerequisites:
```bash
./check-env.sh
```

## New Files Added

### check-env.sh
A comprehensive environment validation script that:
- Checks for required commands (bash, jq, java, zip)
- Checks for optional commands (curl/wget, zipalign, optipng)
- Validates Java version (requires 21+)
- Checks all binary tools (apksigner, dexlib2, paccer, aapt2, htmlq, toml)
- Validates syntax of all library modules
- Checks configuration file validity
- Verifies signing assets (ks.keystore, sig.txt)
- Provides color-coded output and summary

## Configuration Changes

### New Global Defaults in config.toml
The following now properly use defaults from config.toml:
- `arch`: Defaults to "arm64-v8a" (was "all")
- `riplib`: Defaults to "true" (was not properly handled)

### App-Specific Overrides
All apps can now properly override:
- Architecture (`arch`)
- Riplib setting (`riplib`)
- All other existing settings remain the same

## Architecture Support

### Supported Architectures
- **arm64-v8a** (aarch64): Native binaries provided
- **arm-v7a** (armv7l): Native binaries provided
- **x86_64**: Maps to arm64 binaries (requires ARM emulation via qemu-user-static or similar)

### Binary Mapping
The `set_prebuilts()` function in `lib/helpers.sh` handles architecture mapping:
```bash
uname -m output    →    Binary used
aarch64           →    arm64
armv7l             →    arm
x86_64             →    arm64 (with warning)
```

## Documentation Updates

### New Files
- **README.md**: Comprehensive project documentation with quick start guide
- **REFACTORING.md**: This file documenting all changes
- **check-env.sh**: Environment validation script

### Updated Files
- **.gitignore**: Enhanced to ignore more build artifacts and temporary files

## Migration Notes

No user action required. All changes are backward compatible:
- Existing config.toml files will work without modification
- New defaults only apply when values are not explicitly set
- App-specific settings take precedence over global defaults
- x86_64 users will see a warning but builds will proceed

## Future Improvements

Potential enhancements identified but not implemented:
1. Add unit tests for each library module
2. Implement parallel downloading from multiple sources
3. Add checksum verification for downloaded APKs
4. Implement build caching for unchanged apps
5. Add progress indicators for downloads and builds
6. Build native x86_64 binaries for better performance on x86_64 systems
7. Add automatic ARM emulation installation check for x86_64 systems
