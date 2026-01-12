# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

ReVanced Builder: Automated APK patching and building system for ReVanced and RVX (ReVanced Extended) applications. This is a Bash-based system that downloads stock APKs and patches them using ReVanced CLI and patches.

## Essential Commands

### Building

```bash
# Build all enabled apps from config.toml
./build.sh config.toml

# Clean build artifacts
./build.sh clean

# Enable debug logging
export LOG_LEVEL=0
./build.sh config.toml

# Check environment prerequisites
./check-env.sh
```

### CI/CD Utilities

```bash
# Separate config for specific app (used in CI)
./extras.sh separate-config config.toml <app_name> output.toml

# Combine logs from multiple builds
./extras.sh combine-logs <logs_directory>
```

### Testing

```bash
# Syntax check all bash scripts
for f in lib/*.sh; do bash -n "$f" && echo "$f: OK"; done

# Check prerequisites only
bash -n build.sh && bash -c "source utils.sh && check_prerequisites"
```

## Architecture

### Modular Library Structure

The codebase uses a **modular library architecture** where `utils.sh` acts as a loader that sources all modules from `lib/`:

```
utils.sh (loader)
  ↓
lib/
├── logger.sh      - Multi-level logging (DEBUG, INFO, WARN, ERROR)
├── helpers.sh     - General utilities (version comparison, validation)
├── config.sh      - TOML/JSON parsing via tq binary
├── network.sh     - HTTP requests with exponential backoff retry
├── prebuilts.sh   - ReVanced CLI/patches download management
├── download.sh    - APK downloads (APKMirror, Uptodown, Archive.org)
└── patching.sh    - APK patching orchestration
```

**Key point:** Always `source utils.sh` to load all modules. Never source individual lib files directly.

### Build Pipeline Flow

```
Prerequisites Check (Java 21+, jq, zip)
  ↓
Load config.toml (via lib/config.sh → tq binary)
  ↓
Download ReVanced CLI + Patches (lib/prebuilts.sh)
  ├── Supports multiple patch sources (array or single string)
  ├── Downloads CLI once (shared across all sources)
  └── Downloads each patch source separately to temp/<org>-rv/
  ↓
For each enabled app:
  ├── Detect compatible version (if version="auto")
  │   └── Union of compatible versions across all patch sources
  ├── Download stock APK (lib/download.sh - tries sources in order)
  ├── Verify APK signature (against sig.txt)
  ├── Apply patches (lib/patching.sh → revanced-cli)
  │   └── Multiple -p flags passed to CLI (one per patch source)
  ├── Apply optimizations (aapt2, riplib, zipalign)
  └── Sign APK (apksigner.jar with v1+v2 only)
  ↓
Output to build/ directory
```

### Version Resolution Logic

The `version = "auto"` setting in config.toml triggers automatic version detection:

1. Parse patches bundle to find supported versions per patch
2. **Multi-Source Support**: Calculate union of compatible versions across all patch sources
3. Download highest compatible version from configured sources
4. Fallback order: APKMirror → Uptodown → Archive.org

This is handled in `lib/patching.sh:_determine_version()` using `lib/helpers.sh:get_patch_last_supported_ver()`.

**Union Strategy** (for multiple patch sources):
- Collect compatible versions from each patch source
- Select highest version supported by at least one source
- Patches from sources that don't support the selected version are skipped with warnings
- This maximizes compatibility and allows using latest patches even if one source lags behind

### Multi-Source Patch Support

The system supports applying patches from multiple GitHub repositories to a single APK:

**Configuration (Backwards Compatible):**
```toml
# Array syntax (multiple sources)
patches-source = [
  "anddea/revanced-patches",
  "jkennethcarino/privacy-revanced-patches"
]

# Single source (still works)
patches-source = "anddea/revanced-patches"
```

**Implementation Details:**
- `lib/config.sh:toml_get_array_or_string()`: Normalizes string/array to array format
- `lib/prebuilts.sh:get_rv_prebuilts_multi()`: Downloads CLI + all patch sources
- `lib/helpers.sh:get_patch_last_supported_ver()`: Union version detection across sources
- `lib/patching.sh:patch_apk()`: Applies multiple patch bundles with `-p jar1 -p jar2 -p jar3`

**Conflict Resolution:**
- RevancedCLI's natural behavior: last patch wins (based on order of `-p` flags)
- Order in config array defines precedence
- No special conflict detection needed - CLI handles it automatically

**Cache Structure:**
```
temp/
├── anddea-rv/patches-latest.rvp
├── jkennethcarino-rv/patches-v1.0.rvp
└── inotia00-rv/revanced-cli-dev.jar
```
Each organization gets its own cache directory.

### Download Source Fallback

Each app can define multiple download sources. The system tries them in this priority order:

1. **APKMirror** (`apkmirror-dlurl`) - Primary, best reliability
2. **Uptodown** (`uptodown-dlurl`) - Secondary, includes XAPK support
3. **Archive.org** (`archive-dlurl`) - Tertiary, historical versions

All sources in `lib/download.sh` follow the pattern:
- `get_<source>_resp()` - Fetch and cache HTML page
- `get_<source>_vers()` - Extract available versions
- `dl_<source>()` - Download and merge split APKs if needed

### Retry Logic with Exponential Backoff

All network operations in `lib/network.sh` use retry logic:

```
Attempt 1: Immediate
Attempt 2: Wait 2s  (INITIAL_RETRY_DELAY)
Attempt 3: Wait 4s  (exponential backoff)
Attempt 4: Wait 8s
Attempt 5: Wait 16s
Then: Fail
```

Configurable via: `MAX_RETRIES`, `INITIAL_RETRY_DELAY`, `CONNECTION_TIMEOUT`

## Configuration System

### config.toml Structure

```toml
# Global settings (apply to all apps unless overridden)
parallel-jobs = 1
patches-source = "anddea/revanced-patches"
cli-source = "inotia00/revanced-cli"
patches-version = "dev"  # or "latest" or "v2.160.0"
cli-version = "dev"
rv-brand = "RVX"
arch = "arm64-v8a"
riplib = true
enable-aapt2-optimize = true

# Per-app settings (override globals)
[YouTube-Extended]
enabled = true
version = "auto"  # auto-detect compatible version
excluded-patches = "'Enable debug logging'"
patcher-args = ["-e", "Custom branding icon"]
apkmirror-dlurl = "..."
uptodown-dlurl = "..."
```

### Config Parsing Flow

1. `build.sh` calls `toml_prep(config.toml)` from `lib/config.sh`
2. Uses `tq` binary (TOML parser) in `bin/toml/<arch>/tq`
3. Converts TOML → JSON, stores in `__TOML__` global variable
4. Access via: `toml_get <table> <key>`
5. Architecture-specific binaries selected via `set_prebuilts()` in `lib/helpers.sh`

## Important Environment Variables

### Required for Building

```bash
KEYSTORE_PASSWORD        # Keystore password (required)
KEYSTORE_ENTRY_PASSWORD  # Key entry password (required)
KEYSTORE_PATH           # Path to keystore (default: ks.keystore)
KEYSTORE_ALIAS          # Key alias (default: jhc)
```

### Optional Runtime Config

```bash
LOG_LEVEL=0             # Debug logging (0=DEBUG, 1=INFO, 2=WARN, 3=ERROR)
MAX_RETRIES=4           # Network retry attempts
INITIAL_RETRY_DELAY=2   # Initial retry delay in seconds
CONNECTION_TIMEOUT=10   # Connection timeout
GITHUB_TOKEN            # For authenticated GitHub API requests
BUILD_MODE              # Force "dev" or "stable" patches
```

## Binary Tools

All prebuilt binaries are in `bin/` with architecture-specific subdirectories:

- `apksigner.jar` - APK signing (Java)
- `dexlib2.jar` - DEX manipulation (Java)
- `paccer.jar` - Patch integrity checker (Java)
- `aapt2/<arch>/aapt2` - Android Asset Packaging Tool
- `htmlq/<arch>/htmlq` - HTML parser for APKMirror scraping
- `toml/<arch>/tq` - TOML parser

Architecture detection in `lib/helpers.sh:set_prebuilts()` sets these paths based on `uname -m`.

## Logging System

Multi-level logging in `lib/logger.sh`:

```bash
log_debug "Debug info"      # Gray, only shown if LOG_LEVEL=0
log_info "Information"       # Cyan, default level
log_warn "Warning"           # Yellow
epr "Error"                  # Red, non-fatal
abort "Fatal error"          # Red, exits with code 1
pr "Success message"         # Green
log "Build notes"            # Writes to build.md
```

## Security Considerations

### APK Signature Scheme

All built APKs are signed with **v1 and v2 only** (v3/v4 disabled). This is enforced via:

```bash
java -jar bin/apksigner.jar sign \
  --v1-signing-enabled true \
  --v2-signing-enabled true \
  --v3-signing-enabled false \
  --v4-signing-enabled false
```

### Signature Verification

Before patching, `lib/patching.sh:check_sig()` verifies the stock APK's signature against known good signatures in `sig.txt`. This prevents patching modified/malicious APKs.

### CI/CD Security

- Releases only publish from trusted repo (not forks)
- Pull requests can build but cannot publish
- Keystore credentials must be GitHub repository secrets

## Key Functions Reference

### lib/helpers.sh

- `isoneof(value, options...)` - Check if value is in list
- `get_highest_ver()` - Get highest semantic version from stdin
- `get_patch_last_supported_ver(pkg, patch, patches_json)` - Find compatible version for a patch
- `set_prebuilts()` - Set architecture-specific binary paths

### lib/patching.sh

- `build_rv(app_table)` - Main build orchestration for one app
- `_determine_version()` - Auto-detect compatible version
- `_download_stock_apk()` - Try all download sources with fallback
- `_build_patcher_args()` - Construct revanced-cli arguments
- `patch_apk(input, output, args, cli, patches)` - Run patching process
- `merge_splits(bundle, output)` - Merge split APKs into single APK

### lib/download.sh

- `dl_apkmirror(url, version, output, arch, dpi)` - Download from APKMirror
- `dl_uptodown(url, version, output)` - Download from Uptodown (supports XAPK)
- `dl_archive(url, version, output)` - Download from Archive.org

## Code Style (from AGENTS.md)

When modifying Bash scripts, follow these standards:

- Header: `#!/usr/bin/env bash`
- Options: `set -euo pipefail`
- Tests: Use `[[ ... ]]` not `[ ... ]`
- Arrays: Use `mapfile -t`, `read -ra`
- Avoid: `eval`, backticks, unquoted expansions, piping curl to shell
- Prefer: Modern tools (`fd`, `rg`, `jq`) over traditional (`find`, `grep`, `awk`)
- Format: Ensure complexity is O(n) or better, sanitize inputs, no secrets in code

## Common Development Patterns

### Adding a New Download Source

1. Add functions in `lib/download.sh`:
   - `get_<source>_resp(url)`
   - `get_<source>_pkg_name(resp)`
   - `get_<source>_vers(resp)`
   - `dl_<source>(url, version, output, ...)`

2. Update `_download_stock_apk()` in `lib/patching.sh` to add new source to fallback chain

### Adding a New Config Option

1. Add to default values in `build.sh:validate_config_value()`
2. Parse in `build_rv()` in `lib/patching.sh`
3. Document in `CONFIG.md`

### Modifying Build Process

The build logic is in `lib/patching.sh:build_rv()` which delegates to:
- `_determine_version()` - Version detection
- `_download_stock_apk()` - APK acquisition
- `patch_apk()` - Core patching
- `_apply_riplib_optimization()` - Library stripping
- `scripts/aapt2-optimize.sh` - Resource optimization

## Troubleshooting

### Enable Debug Output

```bash
export LOG_LEVEL=0
./build.sh config.toml
```

This shows all `log_debug()` calls, including:
- Config parsing details
- Network request/retry details
- Version detection logic
- Patch compatibility checks

### Common Build Failures

**"Java version must be 21 or higher"**
- Install OpenJDK Temurin 21+
- Check: `java -version`

**"Request failed after 4 retries"**
- Network connectivity issue
- Try different download source in config.toml
- Check if source website is accessible

**"Building 'App-Name' failed"**
- Version incompatibility with patches
- Set `version = "auto"` to auto-detect compatible version
- Check patch changelog for supported versions

**"Keystore password not set"**
- Set `KEYSTORE_PASSWORD` and `KEYSTORE_ENTRY_PASSWORD` environment variables
- For CI: Configure as repository secrets

## Output Artifacts

```
build/          - Final patched APKs
temp/           - Cached downloads, temporary files
logs/           - Build logs (CI mode)
build.md        - Build summary with changelogs
```
