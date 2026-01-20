# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**ReVanced Builder**: Automated APK patching and building system for ReVanced and RVX (ReVanced Extended) applications. This Bash-based system downloads stock APKs and patches them using ReVanced CLI and patches.

**Tech Stack**: Bash, Python 3+, Java 21+, jq, zip

## Table of Contents

1. [Quick Start](#quick-start)
2. [Essential Commands](#essential-commands)
3. [Architecture](#architecture)
4. [Configuration](#configuration)
5. [Security](#security-considerations)
6. [Development Guide](#development-guide)
7. [Troubleshooting](#troubleshooting)
8. [Reference](#reference)

## Quick Start

```bash
# 1. Check prerequisites
./check-env.sh

# 2. Set required environment variables
export KEYSTORE_PASSWORD="your-password"
export KEYSTORE_ENTRY_PASSWORD="your-entry-password"

# 3. Build all enabled apps
./build.sh config.toml

# 4. Find output in build/ directory
```

**Prerequisites**: Java 21+, Python 3+, jq, zip, lxml, cssselect

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
for f in scripts/lib/*.sh; do bash -n "$f" && echo "$f: OK"; done

# Check prerequisites only
bash -n build.sh && bash -c "source utils.sh && check_prerequisites"
```

## Architecture

### Modular Library Structure

The codebase uses a **modular library architecture** where `utils.sh` acts as a loader that sources all modules from `scripts/lib/`:

```text
utils.sh (loader)
  ↓
scripts/lib/
├── logger.sh      - Multi-level logging (DEBUG, INFO, WARN, ERROR)
├── helpers.sh     - General utilities (version comparison, validation, HTML parsing)
├── config.sh      - TOML/JSON parsing via Python (tomllib/jq)
├── network.sh     - HTTP requests with exponential backoff retry
├── cache.sh       - Build cache management with TTL
├── prebuilts.sh   - ReVanced CLI/patches download management
├── download.sh    - APK downloads (APKMirror, Uptodown, Archive.org)
├── patching.sh    - APK patching orchestration
└── checks.sh      - Environment prerequisite validation
```

**Key point:** Always `source utils.sh` to load all modules. Never source individual scripts/lib files directly.

### Build Pipeline Flow

```text
Prerequisites Check (Java 21+, Python 3+, jq, zip)
  ↓
Load config.toml (via scripts/lib/config.sh → Python toml_get.py)
  ↓
Download ReVanced CLI + Patches (scripts/lib/prebuilts.sh)
  ├── Supports multiple patch sources (array or single string)
  ├── Downloads CLI once (shared across all sources)
  └── Downloads each patch source separately to temp/<org>-rv/
  ↓
For each enabled app:
  ├── Detect compatible version (if version="auto")
  │   └── Union of compatible versions across all patch sources
  ├── Download stock APK (scripts/lib/download.sh - tries sources in order)
  │   └── HTML parsing via Python (scripts/html_parser.py)
  ├── Verify APK signature (against assets/sig.txt)
  ├── Apply patches (scripts/lib/patching.sh → revanced-cli)
  │   └── Multiple -p flags passed to CLI (one per patch source)
  ├── Apply optimizations (aapt2, riplib, zipalign)
  └── Sign APK (apksigner.jar with v1+v2 only)
  ↓
Output to build/ directory
```

### Version Resolution Logic

The `version = "auto"` setting in config.toml triggers automatic version detection:

1. Parse patches bundle to find supported versions per patch
1. **Multi-Source Support**: Calculate union of compatible versions across all patch sources
1. Download highest compatible version from configured sources
1. Fallback order: APKMirror → Uptodown → Archive.org

This is handled in `scripts/lib/patching.sh:_determine_version()` using `scripts/lib/helpers.sh:get_patch_last_supported_ver()`.

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

- `scripts/lib/config.sh:toml_get_array_or_string()`: Normalizes string/array to array format
- `scripts/lib/prebuilts.sh:get_rv_prebuilts_multi()`: Downloads CLI + all patch sources
- `scripts/lib/helpers.sh:get_patch_last_supported_ver()`: Union version detection across sources
- `scripts/lib/patching.sh:patch_apk()`: Applies multiple patch bundles with `-p jar1 -p jar2 -p jar3`

**Conflict Resolution:**

- RevancedCLI's natural behavior: last patch wins (based on order of `-p` flags)
- Order in config array defines precedence
- No special conflict detection needed - CLI handles it automatically

**Cache Structure:**

```text
temp/
├── anddea-rv/patches-latest.rvp
├── jkennethcarino-rv/patches-v1.0.rvp
└── inotia00-rv/revanced-cli-dev.jar
```

Each organization gets its own cache directory.

### Download Source Fallback

Each app can define multiple download sources. The system tries them in this priority order:

1. **APKMirror** (`apkmirror-dlurl`) - Primary, best reliability
1. **Uptodown** (`uptodown-dlurl`) - Secondary, includes XAPK support
1. **Archive.org** (`archive-dlurl`) - Tertiary, historical versions

All sources in `scripts/lib/download.sh` follow the pattern:

- `get_<source>_resp()` - Fetch and cache HTML page
- `get_<source>_vers()` - Extract available versions (using scripts/html_parser.py)
- `dl_<source>()` - Download and merge split APKs if needed

### Retry Logic with Exponential Backoff

All network operations in `scripts/lib/network.sh` use retry logic:

```text
Attempt 1: Immediate
Attempt 2: Wait 2s  (INITIAL_RETRY_DELAY)
Attempt 3: Wait 4s  (exponential backoff)
Attempt 4: Wait 8s
Attempt 5: Wait 16s
Then: Fail
```

Configurable via: `MAX_RETRIES`, `INITIAL_RETRY_DELAY`, `CONNECTION_TIMEOUT`

## Configuration

### Environment Variables

**Required:**
- `KEYSTORE_PASSWORD` - Keystore password
- `KEYSTORE_ENTRY_PASSWORD` - Key entry password
- `KEYSTORE_PATH` - Path to keystore (default: ks.keystore)
- `KEYSTORE_ALIAS` - Key alias (default: jhc)

**Optional:**
- `LOG_LEVEL` - Logging level: 0=DEBUG, 1=INFO, 2=WARN, 3=ERROR
- `MAX_RETRIES` - Network retry attempts (default: 4)
- `INITIAL_RETRY_DELAY` - Initial retry delay in seconds (default: 2)
- `CONNECTION_TIMEOUT` - Connection timeout (default: 10)
- `GITHUB_TOKEN` - For authenticated GitHub API requests
- `BUILD_MODE` - Force "dev" or "stable" patches

### config.toml Structure

```toml
# Global settings (apply to all apps unless overridden)
parallel-jobs = 1
patches-source = "anddea/revanced-patches"  # or array: ["source1", "source2"]
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
archive-dlurl = "..."
```

**Key Features:**
- **Multi-source patches**: Use array for multiple patch sources (last wins in conflicts)
- **Auto version detection**: Set `version = "auto"` for automatic compatibility matching
- **Download fallback**: Configure multiple download sources (APKMirror → Uptodown → Archive.org)
- **Global + per-app**: Global settings with per-app overrides

### Config Parsing Implementation

```text
build.sh → toml_prep() → scripts/lib/config.sh
  ↓
Python toml_get.py (uses tomllib)
  ↓
TOML → JSON → __TOML__ global variable
  ↓
Access via: toml_get <table> <key>
```

### Tools & Utilities

**Java Tools** (in `bin/`):
- `apksigner.jar` - APK signing
- `dexlib2.jar` - DEX manipulation
- `paccer.jar` - Patch integrity checker
- `aapt2/<arch>/aapt2` - Android Asset Packaging (auto-detects system binary first)

**Python Scripts** (in `scripts/`):
- `html_parser.py` - HTML parsing with CSS selectors (requires: lxml, cssselect)
- `toml_get.py` - TOML config parsing (uses Python tomllib)

**Logging Functions** (`scripts/lib/logger.sh`):
```bash
log_debug "msg"   # Gray, LOG_LEVEL=0 only
log_info "msg"    # Cyan, default
log_warn "msg"    # Yellow
epr "msg"         # Red error, non-fatal
abort "msg"       # Red error, exits
pr "msg"          # Green success
log "msg"         # Writes to build.md
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

Before patching, `scripts/lib/patching.sh:check_sig()` verifies the stock APK's signature against known good signatures in `assets/sig.txt`. This prevents patching modified/malicious APKs.

### CI/CD Security

- Releases only publish from trusted repo (not forks)
- Pull requests can build but cannot publish
- Keystore credentials must be GitHub repository secrets

## Key Functions Reference

### scripts/lib/helpers.sh

- `isoneof(value, options...)` - Check if value is in list
- `get_highest_ver()` - Get highest semantic version from stdin
- `get_patch_last_supported_ver(pkg, patch, patches_json)` - Find compatible version for a patch
- `set_prebuilts()` - Set architecture-specific binary paths (with aapt2 auto-detection)
- `scrape_text(selector)` - Extract text from HTML via Python parser
- `scrape_attr(selector, attr)` - Extract attribute from HTML via Python parser

### scripts/lib/patching.sh

- `build_rv(app_table)` - Main build orchestration for one app
- `_determine_version()` - Auto-detect compatible version
- `_download_stock_apk()` - Try all download sources with fallback
- `_build_patcher_args()` - Construct revanced-cli arguments
- `patch_apk(input, output, args, cli, patches)` - Run patching process
- `merge_splits(bundle, output)` - Merge split APKs into single APK
- `check_sig(apk, pkg)` - Verify APK signature against known good signatures

### scripts/lib/download.sh

- `dl_apkmirror(url, version, output, arch, dpi)` - Download from APKMirror
- `dl_uptodown(url, version, output)` - Download from Uptodown (supports XAPK)
- `dl_archive(url, version, output)` - Download from Archive.org

## Development Guide

### Code Style Standards

**Bash Scripts:**
- Header: `#!/usr/bin/env bash`
- Options: `set -euo pipefail`
- Tests: Use `[[ ... ]]` not `[ ... ]`
- Arrays: Use `mapfile -t`, `read -ra`
- Avoid: `eval`, backticks, unquoted expansions, piping curl to shell
- Prefer: Modern tools (`fd`, `rg`, `jq`) over traditional (`find`, `grep`, `awk`)
- Performance: O(n) complexity or better, sanitize inputs, no secrets in code

**Module Loading:**
- Always `source utils.sh` to load all library modules
- Never source individual `scripts/lib/*.sh` files directly

### Common Development Tasks

**Adding a Download Source:**

1. Implement in `scripts/lib/download.sh`:
   ```bash
   get_<source>_resp(url)              # Fetch HTML
   get_<source>_pkg_name(resp)         # Extract package name
   get_<source>_vers(resp)             # Extract versions (use scrape_text/scrape_attr)
   dl_<source>(url, version, output)   # Download APK
   ```

2. Add to fallback chain in `scripts/lib/patching.sh:_download_stock_apk()`

**Adding a Config Option:**

1. Add default in `build.sh:validate_config_value()`
2. Parse in `scripts/lib/patching.sh:build_rv()`
3. Document in `CONFIG.md`

**Modifying Build Pipeline:**

Core logic: `scripts/lib/patching.sh:build_rv()` delegates to:
- `_determine_version()` - Version auto-detection
- `_download_stock_apk()` - APK download with fallback
- `patch_apk()` - Patching orchestration
- `_apply_riplib_optimization()` - Library stripping
- `scripts/aapt2-optimize.sh` - Resource optimization

## Troubleshooting

### Debug Mode

Enable detailed logging to diagnose issues:

```bash
export LOG_LEVEL=0  # 0=DEBUG, 1=INFO, 2=WARN, 3=ERROR
./build.sh config.toml
```

Debug output includes:
- Config parsing details
- Network requests and retries
- Version detection logic
- Patch compatibility checks
- Build pipeline steps

### Common Issues

| Error | Cause | Solution |
|-------|-------|----------|
| "Java version must be 21 or higher" | Wrong Java version | Install OpenJDK 21+, verify with `java -version` |
| "Request failed after 4 retries" | Network issue | Check connectivity, try different download source |
| "Building 'App-Name' failed" | Version incompatibility | Use `version = "auto"` in config.toml |
| "Keystore password not set" | Missing env vars | Set `KEYSTORE_PASSWORD` and `KEYSTORE_ENTRY_PASSWORD` |
| "Signature verification failed" | Modified APK | Download stock APK from trusted source |
| "Patch not compatible" | Version mismatch | Check patch changelog, use compatible version |

### Validation Commands

```bash
# Check all prerequisites
./check-env.sh

# Syntax check all Bash scripts
for f in scripts/lib/*.sh; do bash -n "$f" && echo "$f: OK"; done

# Verify config parsing
bash -c "source utils.sh && toml_prep config.toml && toml_get YouTube-Extended enabled"

# Test download source
./build.sh config.toml  # Add specific app to test
```

## Reference

### Project Structure

```text
.
├── build.sh              - Main build script
├── utils.sh              - Module loader
├── check-env.sh          - Prerequisites checker
├── extras.sh             - CI/CD utilities
├── config.toml           - Build configuration
├── scripts/
│   ├── lib/              - Core modules (source via utils.sh)
│   │   ├── logger.sh     - Logging system
│   │   ├── helpers.sh    - Utilities
│   │   ├── config.sh     - Config parsing
│   │   ├── network.sh    - HTTP client
│   │   ├── cache.sh      - Cache management
│   │   ├── prebuilts.sh  - CLI/patches download
│   │   ├── download.sh   - APK downloads
│   │   ├── patching.sh   - Build orchestration
│   │   └── checks.sh     - Environment checks
│   ├── html_parser.py    - HTML scraping
│   └── toml_get.py       - TOML parser
├── bin/                  - Prebuilt binaries
├── assets/sig.txt        - Known APK signatures
├── build/                - Output APKs
└── temp/                 - Cache & temporary files
```

### Output Artifacts

| Path | Description |
|------|-------------|
| `build/` | Final patched APKs |
| `temp/` | Cached downloads, temporary files |
| `temp/<org>-rv/` | Per-organization patch caches |
| `logs/` | Build logs (CI mode only) |
| `build.md` | Build summary with changelogs |

### Quick Command Reference

```bash
# Building
./build.sh config.toml                    # Build all enabled apps
./build.sh clean                          # Clean artifacts
LOG_LEVEL=0 ./build.sh config.toml        # Debug build

# CI/CD
./extras.sh separate-config config.toml youtube out.toml
./extras.sh combine-logs logs/

# Testing
./check-env.sh                            # Check prerequisites
bash -n build.sh                          # Syntax check
```
