# AGENTS.md

This file provides comprehensive guidance for AI coding assistants (Claude Code, GitHub Copilot, Google Gemini Code Assist, Cursor, etc.) when working with this repository.

## Project Overview

**ReVanced Builder** is an automated APK patching and building system for ReVanced and RVX (ReVanced Extended) applications. This is a production-grade Bash-based system that downloads stock Android APKs and patches them using ReVanced CLI and patch bundles from multiple sources.

### Tech Stack

- **Primary Language**: Bash 4.0+ (22 scripts, ~2,900 LOC)
- **Utilities**: Python 3.11+ (HTML parsing, TOML parsing)
- **Configuration**: TOML (with JSON intermediate format)
- **Build System**: Make + Bash orchestration
- **CI/CD**: GitHub Actions (8 workflows, 1,201 LOC)
- **Linting Stack**: ShellCheck, shfmt, shellharden, Ruff, yamllint, taplo, Biome
- **Testing**: Bash unit tests with fixtures
- **Binary Tools**: Java-based (apksigner, dexlib2) + native (aapt2)

### Key Features

- **Multi-source patch support**: Apply patches from multiple GitHub repositories
- **Automatic version detection**: Find compatible versions across patch sources
- **Intelligent fallback**: Download from APKMirror → Uptodown → Archive.org
- **Build caching**: TTL-based caching with integrity validation
- **Network resilience**: Exponential backoff retry (max 5 attempts)
- **Modular architecture**: 9 library modules loaded via single entry point
- **Comprehensive linting**: 6 different linters with auto-fix support
- **CI/CD automation**: Daily builds, manual triggers, PR validation

## Repository Structure

```
@build.sh                       # Main build orchestration (~13.5KB)
@utils.sh                       # Module loader - source this to load all libs
@check-env.sh                   # Prerequisites validation
@extras.sh                      # CI/CD utilities (config separation, log combining)
@config.toml                    # Main configuration file
@Makefile                       # Build targets: lint, format, install-tools, test-syntax

@scripts/lib/                   # Core modular libraries (2,726 LOC)
  @logger.sh                    # Multi-level logging system
  @helpers.sh                   # Version comparison, validation, HTML parsing
  @config.sh                    # TOML/JSON parsing via Python tomllib
  @network.sh                   # HTTP with exponential backoff retry
  @cache.sh                     # Build cache with TTL
  @prebuilts.sh                 # CLI/patches download management
  @download.sh                  # APK downloads (APKMirror/Uptodown/Archive.org)
  @patching.sh                  # APK patching orchestration
  @checks.sh                    # Environment prerequisite checks

@scripts/                       # Python utilities and shell helpers
  @html_parser.py               # CSS selector-based HTML parsing (lxml)
  @toml_get.py                  # TOML→JSON converter (tomllib)
  @apkmirror_search.py          # APKMirror version extraction
  @uptodown_search.py           # Uptodown version extraction
  lint.sh                       # Comprehensive linting orchestration
  changelog-generator.sh        # Changelog automation
  dependency-checker.sh         # Dependency monitoring
  aapt2-optimize.sh             # Resource optimization
  release-manager.sh            # Release automation

@bin/                           # Prebuilt binaries
  apksigner.jar                 # APK signing (v1+v2 only)
  dexlib2.jar                   # DEX manipulation
  paccer.jar                    # Patch integrity checker
  aapt2/                        # Android Asset Packaging (arch-specific)

@assets/
  sig.txt                       # Known good APK signatures
  ks.keystore                   # Signing keystore

@tests/                         # Testing infrastructure
  test_apkmirror_search.sh      # APKMirror parser tests
  test-multi-source.sh          # Multi-source patching tests
  benchmark_download.sh         # Performance benchmarks
  fixtures/                     # Test data (HTML mocks)

@.github/
  workflows/                    # 8 GitHub Actions workflows
  instructions/                 # Code style guides
  ISSUE_TEMPLATE/               # Issue templates

Configuration Files:
  .shellcheckrc                 # ShellCheck rules
  .editorconfig                 # Editor settings
  .yamllint.yml                 # YAML linting rules
  .yamlfmt                      # YAML formatting
  .taplo.toml                   # TOML formatting
  biome.json                    # Biome (JSON/HTML/JS/TS/CSS)
  pyproject.toml                # Python tools (Ruff)
  .pre-commit-config.yaml       # Pre-commit hooks

Documentation:
  README.md                     # User guide
  CONFIG.md                     # Configuration reference
  CLAUDE.md → AGENTS.md         # AI assistant guide (symlink)
  GEMINI.md → AGENTS.md         # AI assistant guide (symlink)
  LINTING.md                    # Linting guide
  PRD.md                        # Product requirements
```

## Development Workflows

### Initial Setup

```bash
# 1. Check prerequisites
./check-env.sh

# 2. Install linting/formatting tools
make install-tools

# 3. Set up pre-commit hooks
make setup-pre-commit

# 4. Configure secrets (for building)
export KEYSTORE_PASSWORD="your-password"
export KEYSTORE_ENTRY_PASSWORD="your-entry-password"
export KEYSTORE_PATH="assets/ks.keystore"  # default
export KEYSTORE_ALIAS="jhc"                # default

# 5. Optional: Enable debug logging
export LOG_LEVEL=0  # 0=DEBUG, 1=INFO, 2=WARN, 3=ERROR
```

**Prerequisites:**
- Bash 4.0+
- Java 21+ (OpenJDK Temurin)
- Python 3.11+ with pip
- System tools: jq, zip, curl/wget
- Optional: optipng (asset optimization)

### Build Workflow

```bash
# Build all enabled apps from config
./build.sh config.toml

# Clean build artifacts
./build.sh clean

# Check environment only (no build)
./check-env.sh
```

**Build Pipeline Flow:**
```
Prerequisites Check → Load config.toml → Download CLI + Patches
  ↓
For each enabled app:
  ├── Detect compatible version (if version="auto")
  ├── Download stock APK (tries: APKMirror → Uptodown → Archive.org)
  ├── Verify APK signature
  ├── Apply patches (multi-source with -p flags)
  ├── Apply optimizations (aapt2, riplib, zipalign)
  └── Sign APK (v1+v2 schemes)
  ↓
Output to build/ directory
```

### Testing Workflow

```bash
# Run all linters (check only)
make lint

# Syntax check all bash scripts
make test-syntax

# Or check individual scripts
bash -n build.sh
bash -n scripts/lib/*.sh

# Run unit tests
./tests/test_apkmirror_search.sh
./tests/test-multi-source.sh

# Performance benchmarking
./tests/benchmark_download.sh
```

### Linting and Formatting

```bash
# Check all files (lint only)
make lint

# Auto-fix all formatting issues
make format

# Run specific linters
./scripts/lint.sh              # all linters
./scripts/lint.sh --fix        # auto-fix mode
```

**Linting Stack by File Type:**
- **Python** (.py): Ruff (linting + formatting) - replaces black, isort, flake8
- **Shell** (.sh): ShellCheck (static analysis), shfmt (formatting), shellharden (hardening)
- **YAML** (.yml, .yaml): yamllint, yamlfmt
- **TOML** (.toml): taplo
- **JSON/HTML/JS/TS/CSS**: Biome

### CI/CD Utilities

```bash
# Separate config for specific app (used in CI matrix)
./extras.sh separate-config config.toml <app_name> output.toml

# Combine logs from multiple builds
./extras.sh combine-logs <logs_directory>

# Generate CI matrix
./scripts/generate_matrix.sh config.toml
```

### Deployment Workflow

**Automated (via GitHub Actions):**
- **Daily Build**: Runs at 06:00 UTC, checks for updates, publishes to "latest" release
- **Manual Build**: On-demand via workflow_dispatch with app selection
- **PR Build**: Validates syntax and runs tests (no publishing)

**Manual Release:**
```bash
# 1. Build locally
./build.sh config.toml

# 2. Use release manager
./scripts/release-manager.sh

# 3. Or manually push to GitHub Releases
gh release create v1.0.0 build/*.apk --title "Release v1.0.0"
```

## Code Conventions

### Bash Style Guide

**Script Headers:**
```bash
#!/usr/bin/env bash
set -euo pipefail
```

**Variable Naming:**
- Global variables: `UPPER_CASE`
- Local variables: `lower_case`
- Function names: `snake_case`
- Constants: `readonly CONSTANT_NAME`

**Best Practices:**
- Use `[[ ... ]]` for tests, NOT `[ ... ]`
- Quote all variable expansions: `"${var}"`
- Use arrays: `mapfile -t arr`, `read -ra arr`
- Prefer `printf` over `echo` for formatted output
- Use `local` for function-scoped variables
- Check command existence: `command -v tool >/dev/null 2>&1`

**Avoid:**
- `eval` (security risk)
- Backticks (use `$( )` instead)
- Unquoted expansions
- Piping curl to shell
- Global variable pollution

**Preferred Tools:**
- `fd` over `find` (when available)
- `rg` over `grep` (when available)
- `jq` for JSON parsing
- Python's `tomllib` for TOML parsing

**Error Handling:**
```bash
# Use abort() for fatal errors
abort "Build failed: incompatible version"

# Use epr() for non-fatal errors
epr "Warning: optimization skipped"

# Check exit codes
if ! some_command; then
    log_warn "Command failed but continuing"
fi
```

### Python Style Guide

**Code Style:**
- Use Ruff for formatting and linting
- Type hints for function signatures
- Docstrings for public functions
- Follow PEP 8 conventions

**Example:**
```python
def scrape_text(html: str, selector: str) -> list[str]:
    """Extract text from HTML using CSS selector.

    Args:
        html: HTML content as string
        selector: CSS selector pattern

    Returns:
        List of extracted text strings
    """
    tree = html.fromstring(html)
    return tree.cssselect(selector)
```

### Configuration Patterns

**TOML Configuration:**
```toml
# Global settings (apply to all apps unless overridden)
parallel-jobs = 1
patches-source = ["anddea/revanced-patches", "jkennethcarino/privacy-revanced-patches"]
cli-source = "inotia00/revanced-cli"
rv-brand = "RVX"

# Per-app settings (override globals)
[YouTube-Extended]
enabled = true
version = "auto"  # auto-detect compatible version
excluded-patches = "'Enable debug logging'"
apkmirror-dlurl = "https://www.apkmirror.com/..."
uptodown-dlurl = "https://..."
```

**Config Access Pattern:**
```bash
# Always source utils.sh first (loads all modules)
source utils.sh

# Prepare config (TOML → JSON)
toml_prep "config.toml"

# Access values
local app_name=$(toml_get "YouTube-Extended" "app-name")
local version=$(toml_get "YouTube-Extended" "version")

# Array support
local patches_sources=$(toml_get_array_or_string "YouTube-Extended" "patches-source")
```

### Module Architecture Patterns

**Module Loading (via utils.sh):**
```bash
#!/usr/bin/env bash
set -euo pipefail

# Load all library modules in dependency order
source scripts/lib/logger.sh
source scripts/lib/helpers.sh
source scripts/lib/config.sh
source scripts/lib/network.sh
source scripts/lib/cache.sh
source scripts/lib/prebuilts.sh
source scripts/lib/download.sh
source scripts/lib/patching.sh
source scripts/lib/checks.sh
```

**ALWAYS** source `utils.sh` to load all modules. Never source individual `scripts/lib/` files directly.

**Logging Pattern:**
```bash
log_debug "Detailed debug information"    # Gray, LOG_LEVEL=0
log_info "General information"             # Cyan, default
log_warn "Warning message"                 # Yellow
epr "Error occurred"                       # Red, non-fatal
abort "Fatal error"                        # Red, exits with 1
pr "Success message"                       # Green
log "Notes for build.md"                   # Writes to build.md
```

**Network Request Pattern:**
```bash
# With automatic retry (exponential backoff)
local response=$(req "https://api.example.com/data")

# With custom retry count
local response=$(req "https://slow-api.com" 10)

# Retry logic: 0s → 2s → 4s → 8s → 16s → fail
```

**Cache Pattern:**
```bash
# Check cache first
if is_cached "resource-key"; then
    log_debug "Using cached resource"
    local path=$(get_cached_path "resource-key")
else
    # Download and cache
    download_resource "output.bin"
    cache_resource "resource-key" "output.bin"
fi
```

### Naming Conventions

**Files:**
- Bash scripts: `kebab-case.sh`
- Python scripts: `snake_case.py`
- Config files: `.lowercase` or `UPPERCASE.md`
- Test files: `test_*.sh` or `*_test.sh`

**Functions (Bash):**
- Public functions: `snake_case` (e.g., `build_rv`, `patch_apk`)
- Private functions: `_snake_case` (leading underscore, e.g., `_determine_version`)
- Validation functions: `check_*` or `validate_*`
- Getter functions: `get_*`

**Variables:**
- Environment variables: `UPPER_SNAKE_CASE`
- Global constants: `readonly UPPER_SNAKE_CASE`
- Local variables: `lower_snake_case`
- Temporary files: `temp/<org>-rv/*`

**Git Branches:**
- Feature: `feature/description`
- Fix: `fix/description`
- AI agent: `claude/description-<session-id>`

## Architecture Details

### Modular Library Structure

The codebase uses a **modular library architecture** where `utils.sh` acts as a loader that sources all modules from `scripts/lib/`:

```text
utils.sh (loader)
  ↓
scripts/lib/
├── logger.sh      - Multi-level logging (DEBUG, INFO, WARN, ERROR)
├── helpers.sh     - General utilities (version comparison, validation, HTML parsing)
├── config.sh      - TOML/JSON parsing via Python tomllib
├── network.sh     - HTTP requests with exponential backoff retry
├── cache.sh       - Build cache management with TTL
├── prebuilts.sh   - ReVanced CLI/patches download management
├── download.sh    - APK downloads (APKMirror, Uptodown, Archive.org)
├── patching.sh    - APK patching orchestration
└── checks.sh      - Environment prerequisite validation
```

**Key point:** Always `source utils.sh` to load all modules. Never source individual scripts/lib files directly.

### Version Resolution Logic

The `version = "auto"` setting in config.toml triggers automatic version detection:

1. Parse patches bundle to find supported versions per patch
2. **Multi-Source Support**: Calculate union of compatible versions across all patch sources
3. Download highest compatible version from configured sources
4. Fallback order: APKMirror → Uptodown → Archive.org

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

### Download Source Fallback

Each app can define multiple download sources. The system tries them in this priority order:

1. **APKMirror** (`apkmirror-dlurl`) - Primary, best reliability
2. **Uptodown** (`uptodown-dlurl`) - Secondary, includes XAPK support
3. **Archive.org** (`archive-dlurl`) - Tertiary, historical versions

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

## Dependencies

### Runtime Dependencies

**System Requirements:**
```bash
# Required
bash >= 4.0
java >= 21          # OpenJDK Temurin recommended
python >= 3.11      # For tomllib support
jq                  # JSON parsing
zip                 # APK manipulation
curl or wget        # HTTP downloads

# Optional
optipng             # PNG optimization
```

**Python Packages (pyproject.toml):**
```toml
dependencies = [
    "lxml>=5.2.2",       # HTML parsing
    "cssselect>=1.2.0",  # CSS selectors
]

[tool.uv]
dev-dependencies = [
    "ruff>=0.8.0",       # Linting + formatting
]
```

**Installation:**
```bash
# Using pip
pip install -e .

# Using uv (faster)
uv pip install -e .
```

### Development Dependencies

**Linting/Formatting Tools:**
```bash
# Shell
shellcheck          # Static analysis
shfmt               # Formatting
shellharden         # Security hardening

# YAML
yamllint            # Linting
yamlfmt             # Formatting

# TOML
taplo-cli           # Formatting

# Web (JSON, HTML, JS, TS, CSS)
biome               # All-in-one linter/formatter

# Python
ruff                # Linting + formatting
```

**Installation:**
```bash
make install-tools  # Installs all tools
```

### Binary Dependencies (Prebuilt)

Located in `bin/`:
- `apksigner.jar` - APK signing (Java)
- `dexlib2.jar` - DEX manipulation (Java)
- `paccer.jar` - Patch integrity validation (Java)
- `aapt2/<arch>/aapt2` - Android Asset Packaging Tool (arch-specific ELF binaries)

**No external downloads required** - all binaries are committed to repo.

## Common Tasks

### Adding a New Download Source

1. **Add functions to `scripts/lib/download.sh`:**

```bash
# Fetch and cache HTML page
get_newsource_resp() {
    local url=$1
    req "${url}"
}

# Extract package name
get_newsource_pkg_name() {
    local resp=$1
    echo "${resp}" | python3 scripts/html_parser.py --text "div.package-name"
}

# Extract available versions
get_newsource_vers() {
    local resp=$1
    echo "${resp}" | python3 scripts/html_parser.py --text "span.version" | \
        tr ' ' '\n' | sort -V
}

# Download APK
dl_newsource() {
    local url=$1 version=$2 output=$3

    log_info "Downloading ${version} from NewsSource"

    # Implementation here
    # Use req() for network requests
    # Use scrape_text() and scrape_attr() for HTML parsing

    pr "Downloaded: ${output}"
}
```

2. **Update `_download_stock_apk()` in `scripts/lib/patching.sh`:**

```bash
# Add to fallback chain
if [[ -n ${newsource_url} ]]; then
    dl_newsource "${newsource_url}" "${version}" "${output}" && return 0
fi
```

3. **Update `config.toml` schema:**

```toml
[App-Name]
newsource-dlurl = "https://newsource.com/app-page"
```

### Adding a New Config Option

1. **Add default value in `build.sh:validate_config_value()`:**

```bash
validate_config_value() {
    local key=$1 default=$2
    local value=$(toml_get "global" "${key}")
    echo "${value:-${default}}"
}

# Add new option
MY_NEW_OPTION=$(validate_config_value "my-new-option" "default-value")
```

2. **Access in modules:**

```bash
# In scripts/lib/patching.sh or other module
local my_option=$(toml_get "${app_table}" "my-new-option")
my_option=${my_option:-${MY_NEW_OPTION}}  # Fallback to global

log_debug "Using option: ${my_option}"
```

3. **Document in `CONFIG.md`:**

```markdown
### `my-new-option`

- Type: string/boolean/integer
- Default: `default-value`
- Description: What this option does...
```

### Adding a New Patch Source

The system already supports multiple patch sources. To use additional sources:

**In `config.toml`:**
```toml
# Array syntax (multiple sources)
patches-source = [
    "anddea/revanced-patches",
    "jkennethcarino/privacy-revanced-patches",
    "your-org/your-patches"  # Add new source
]
```

**No code changes needed** - the system automatically:
- Downloads all patch bundles
- Detects compatible versions across all sources (union)
- Applies patches with multiple `-p` flags to CLI

### Debugging Build Failures

**Enable debug logging:**
```bash
export LOG_LEVEL=0
./build.sh config.toml 2>&1 | tee build-debug.log
```

**Common issues and solutions:**

| Error | Cause | Solution |
|-------|-------|----------|
| "Java version must be 21 or higher" | Old Java | Install OpenJDK Temurin 21+ |
| "Request failed after 5 retries" | Network issue | Check connectivity, try different download source |
| "Building 'App' failed" | Version incompatibility | Set `version = "auto"` in config |
| "Keystore password not set" | Missing env var | Export `KEYSTORE_PASSWORD` and `KEYSTORE_ENTRY_PASSWORD` |
| "Signature verification failed" | Modified APK | Check APK source, verify hash |
| "Patch not found" | Invalid patch name | Check patch list in `.rvp` bundle |

**Debug specific components:**
```bash
# Test config parsing
source utils.sh
toml_prep config.toml
toml_get "YouTube-Extended" "version"

# Test download source
bash tests/test_apkmirror_search.sh

# Test multi-source patching
bash tests/test-multi-source.sh

# Benchmark performance
bash tests/benchmark_download.sh
```

### Modifying the Build Process

**Build orchestration is in `scripts/lib/patching.sh:build_rv()`:**

```bash
build_rv() {
    local app_table=$1

    # 1. Version detection
    version=$(_determine_version "${app_table}")

    # 2. Download stock APK
    _download_stock_apk "${app_table}" "${version}" "${stock_apk}"

    # 3. Verify signature
    check_sig "${stock_apk}" "${package_name}"

    # 4. Apply patches
    patch_apk "${stock_apk}" "${patched_apk}" "${patcher_args}" "${cli_jar}" "${patches_jars[@]}"

    # 5. Optimizations
    if [[ ${riplib} == true ]]; then
        _apply_riplib_optimization "${patched_apk}"
    fi

    if [[ ${aapt2_optimize} == true ]]; then
        scripts/aapt2-optimize.sh "${patched_apk}"
    fi

    # 6. Sign APK
    sign_apk "${patched_apk}"

    # 7. Move to build/
    mv "${patched_apk}" "build/${app_name}-${version}.apk"
}
```

**To modify:**
1. Edit relevant function in `scripts/lib/patching.sh`
2. Test with single app: `./build.sh config.toml`
3. Run syntax check: `bash -n scripts/lib/patching.sh`
4. Run linter: `make lint`

### Adding Pre-commit Hooks

**Edit `.pre-commit-config.yaml`:**
```yaml
repos:
  - repo: local
    hooks:
      - id: my-custom-hook
        name: My Custom Hook
        entry: scripts/my-hook.sh
        language: system
        types: [shell]
        pass_filenames: false
```

**Install hooks:**
```bash
make setup-pre-commit
```

### Creating a New GitHub Workflow

**Template for new workflow in `.github/workflows/`:**
```yaml
name: My Workflow

on:
  workflow_dispatch:
    inputs:
      param:
        description: 'Parameter description'
        required: true

jobs:
  my-job:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up environment
        run: |
          ./check-env.sh

      - name: Run task
        env:
          KEYSTORE_PASSWORD: ${{ secrets.KEYSTORE_PASSWORD }}
        run: |
          ./build.sh config.toml
```

**Test locally with act:**
```bash
act workflow_dispatch -j my-job
```

## Security Best Practices

### APK Signature Verification

Before patching, always verify APK signature:

```bash
# In scripts/lib/patching.sh:check_sig()
check_sig() {
    local apk=$1 pkg=$2

    # Extract signature
    local sig=$(java -jar bin/apksigner.jar verify --print-certs "${apk}" | \
                grep "SHA-256" | awk '{print $2}')

    # Verify against known good signatures
    if ! grep -q "${sig}" assets/sig.txt; then
        abort "Signature verification failed for ${pkg}"
    fi
}
```

### Signing Configuration

APKs are signed with **v1 and v2 only** (v3/v4 disabled):

```bash
java -jar bin/apksigner.jar sign \
  --ks "${KEYSTORE_PATH}" \
  --ks-pass "pass:${KEYSTORE_PASSWORD}" \
  --ks-key-alias "${KEYSTORE_ALIAS}" \
  --key-pass "pass:${KEYSTORE_ENTRY_PASSWORD}" \
  --v1-signing-enabled true \
  --v2-signing-enabled true \
  --v3-signing-enabled false \
  --v4-signing-enabled false \
  --out "${signed_apk}" \
  "${unsigned_apk}"
```

### Secrets Management

**Never commit secrets to the repository:**
- ✅ Use environment variables
- ✅ Use GitHub secrets for CI/CD
- ✅ Add to `.gitignore`
- ❌ Hardcode passwords in scripts
- ❌ Commit `.env` files

**CI/CD secrets:**
```yaml
env:
  KEYSTORE_PASSWORD: ${{ secrets.KEYSTORE_PASSWORD }}
  KEYSTORE_ENTRY_PASSWORD: ${{ secrets.KEYSTORE_ENTRY_PASSWORD }}
```

## Performance Optimization

### Recent Performance Improvements

The codebase has undergone significant optimization (6.5x+ speedups):

1. **Python TOML Parsing**: Replaced external `tq` binary with native Python `tomllib`
2. **Python HTML Parsing**: Replaced `htmlq` binary with `lxml` + `cssselect`
3. **Network Caching**: Aggressive caching of HTTP responses with TTL
4. **Build Caching**: Cache CLI/patches downloads between builds
5. **Parallel Builds**: Matrix strategy in CI/CD for concurrent app builds

### Performance Best Practices

**Do:**
- ✅ Cache HTTP responses
- ✅ Use build cache for repeated downloads
- ✅ Run independent builds in parallel
- ✅ Use native Python/Bash instead of spawning subprocesses
- ✅ Stream large files instead of loading into memory

**Don't:**
- ❌ Parse JSON/TOML with `awk`/`sed`
- ❌ Use nested loops for large datasets (keep O(n) complexity)
- ❌ Download same file multiple times
- ❌ Run sequential builds when parallelization is possible
- ❌ Use excessive subprocess spawning in loops

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

## Environment Variables

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

## Output Artifacts

```text
build/          - Final patched APKs
temp/           - Cached downloads, temporary files
logs/           - Build logs (CI mode)
build.md        - Build summary with changelogs
```

## Additional Resources

- **README.md** - User-facing documentation
- **CONFIG.md** - Configuration reference
- **LINTING.md** - Linting guide and tool documentation
- **PRD.md** - Product requirements and roadmap
- **.github/instructions/** - Detailed code style guides

## Key Takeaways for AI Assistants

1. **Always source `utils.sh`** - Never source individual `scripts/lib/` files directly
2. **Use logging functions** - Don't use `echo` or `printf` for user-facing messages
3. **Follow Bash best practices** - Use `[[ ]]`, quote expansions, use `local`, avoid `eval`
4. **Run linters before committing** - `make lint` or `make format`
5. **Test thoroughly** - Run `make test-syntax` and relevant unit tests
6. **Enable debug logging** - `export LOG_LEVEL=0` when troubleshooting
7. **Use existing patterns** - Follow established conventions for new features
8. **Document changes** - Update relevant `.md` files when modifying behavior
9. **Security first** - Verify signatures, use v1+v2 signing only, never commit secrets
10. **Performance matters** - Cache aggressively, use native tools, avoid O(n²) complexity

---

**Last updated**: 2026-02-10
**Repository**: https://github.com/Ven0m0/Revanced-auto
