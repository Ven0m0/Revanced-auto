# ReVanced Builder - Library Modules

This directory contains modular components for the ReVanced builder, refactored from the original monolithic `utils.sh` file for better maintainability, testability, and performance.

## Architecture

The codebase has been refactored into the following modules:

```
lib/
├── logger.sh      - Logging and messaging functions
├── helpers.sh     - General utility functions
├── config.sh      - Configuration parsing (TOML/JSON)
├── network.sh     - HTTP requests with retry logic
├── prebuilts.sh   - ReVanced CLI & patches management
├── download.sh    - APK downloads (APKMirror, Uptodown, Archive.org)
└── patching.sh    - APK patching and building
```

## Module Descriptions

### logger.sh
**Purpose**: Centralized logging with multiple log levels

**Functions**:
- `pr(msg)` - Print success message in green
- `log_info(msg)` - Info level logging (cyan)
- `log_debug(msg)` - Debug level logging (gray)
- `log_warn(msg)` - Warning level logging (yellow)
- `epr(msg)` - Error message in red
- `abort(msg)` - Fatal error, exits with error
- `log(msg)` - Write to build.md file

**Log Levels**:
- `LOG_LEVEL_DEBUG=0` - All messages
- `LOG_LEVEL_INFO=1` - Info and above (default)
- `LOG_LEVEL_WARN=2` - Warnings and errors only
- `LOG_LEVEL_ERROR=3` - Errors only

Set log level: `export LOG_LEVEL=0` for debug mode

### helpers.sh
**Purpose**: General utility functions

**Functions**:
- `isoneof(value, options...)` - Check if value is in list
- `get_highest_ver()` - Get highest semantic version from stdin
- `semver_validate(version)` - Validate semantic version format
- `list_args(string)` - Convert space-separated to newline-separated
- `join_args(string, prefix)` - Join arguments with prefix
- `get_patch_last_supported_ver(...)` - Get compatible patch version
- `set_prebuilts()` - Set binary tool paths based on architecture

### config.sh
**Purpose**: Configuration file parsing and management

**Functions**:
- `toml_prep(file)` - Load TOML or JSON config file
- `toml_get_table_names()` - Get all table names
- `toml_get_table_main()` - Get main (non-table) config
- `toml_get_table(name)` - Get specific table
- `toml_get(table, key)` - Get value from table
- `vtf(value, field)` - Validate boolean field
- `config_update()` - Check for patch updates

**Global Variables**:
- `__TOML__` - Parsed configuration (JSON format)

### network.sh
**Purpose**: HTTP requests with exponential backoff retry logic

**Features**:
- Automatic retries with exponential backoff
- Concurrent download protection
- File caching (skips if exists)
- Cookie persistence
- GitHub API authentication

**Functions**:
- `req(url, output)` - Standard HTTP request
- `gh_req(url, output)` - GitHub API request (authenticated)
- `gh_dl(file, url)` - GitHub asset download

**Configuration**:
- `MAX_RETRIES=4` - Maximum retry attempts
- `INITIAL_RETRY_DELAY=2` - Initial delay in seconds
- `CONNECTION_TIMEOUT=10` - Connection timeout

**Retry Schedule**: 2s → 4s → 8s → 16s → fail

### prebuilts.sh
**Purpose**: ReVanced CLI and patches management

**Functions**:
- `get_rv_prebuilts(cli_src, cli_ver, patches_src, patches_ver)` - Download/locate prebuilts
- `_remove_integrations_checks(file)` - Remove integrity checks from patches

**Supported Versions**:
- `dev` - Latest development version
- `latest` - Latest stable release
- `v1.2.3` - Specific version tag

**Output**: Space-separated paths to CLI JAR and patches file

### download.sh
**Purpose**: APK downloads from multiple sources

**Supported Sources**:
1. **APKMirror** - Primary source, best compatibility
2. **Uptodown** - Secondary source, includes XAPK support
3. **Archive.org** - Tertiary source, historical versions

**Functions per source**:
- `get_<source>_resp(url)` - Fetch and cache page
- `get_<source>_pkg_name()` - Extract package name
- `get_<source>_vers()` - List available versions
- `dl_<source>(url, version, output, arch, dpi)` - Download APK

**Features**:
- Bundle/split APK merging
- Architecture filtering (arm64-v8a, arm-v7a, all)
- DPI selection (for APKMirror)
- Alpha/beta version filtering

### patching.sh
**Purpose**: APK patching and building

**Main Functions**:
- `build_rv(args)` - Main build orchestration
- `patch_apk(input, output, args, cli, patches)` - Patch APK with ReVanced
- `check_sig(apk, pkg)` - Verify APK signature
- `merge_splits(bundle, output)` - Merge split APKs

**Helper Functions**:
- `_determine_version(...)` - Auto-detect compatible version
- `_build_patcher_args()` - Build CLI arguments
- `_download_stock_apk(...)` - Download from available sources
- `_handle_microg_patch(...)` - Auto-handle MicroG patches
- `_apply_riplib_optimization(...)` - Strip unnecessary libraries

**Build Modes**:
- `apk` - Non-root APK (direct install)
- `module` - Magisk module (root install)
- `both` - Build both variants

## Key Improvements

### 1. Modularity
- **Before**: Single 594-line utils.sh file
- **After**: 7 focused modules (~200 lines each)
- **Benefit**: Easier to understand, test, and maintain

### 2. Error Handling
- **Before**: Inconsistent error messages, no retry logic
- **After**: Standardized logging, exponential backoff retries
- **Benefit**: More reliable network operations, better debugging

### 3. Code Reusability
- **Before**: Duplicated logic across functions
- **After**: Shared helper functions
- **Benefit**: DRY principle, fewer bugs

### 4. Logging
- **Before**: Only success/error messages
- **After**: Multi-level logging (debug, info, warn, error)
- **Benefit**: Better debugging and monitoring

### 5. Performance
- **Before**: No retry logic, hardcoded timeouts
- **After**: Smart retries, configurable timeouts, better caching
- **Benefit**: Faster builds, fewer failures

### 6. Build Function
- **Before**: 150+ line build_rv() function
- **After**: Broken into 6 focused helper functions
- **Benefit**: Easier to understand and modify

## Usage

### Loading Modules
```bash
source utils.sh  # Automatically loads all modules
```

### Debug Mode
```bash
export LOG_LEVEL=0  # Enable debug logging
./build.sh config.toml
```

### Custom Retry Configuration
```bash
export MAX_RETRIES=6
export INITIAL_RETRY_DELAY=1
./build.sh config.toml
```

## Dependencies

### Required Tools
- `bash` >= 4.0
- `jq` - JSON parsing
- `java` >= 11 - APK patching
- `zip` - Archive creation
- `curl` - HTTP requests

### Architecture-Specific Binaries
Located in `bin/`:
- `aapt2` - Android Asset Packaging Tool
- `htmlq` - HTML parsing (for APKMirror)
- `tq` - TOML parsing
- `apksigner.jar` - APK signing
- `dexlib2.jar` - DEX manipulation
- `paccer.jar` - Patch integrity checker

## Testing

### Syntax Check
```bash
for f in lib/*.sh; do bash -n "$f" && echo "$f: OK"; done
```

### Dry Run
```bash
# Check prerequisites only
bash -n build.sh && bash -c "source utils.sh && check_prerequisites"
```

## Migration Notes

The refactoring maintains **100% backward compatibility**. All original function names and behaviors are preserved. The new modular structure is transparent to:

- `build.sh` (updated for improvements)
- `build-termux.sh` (no changes needed)
- CI/CD workflows (no changes needed)
- User configurations (no changes needed)

## Future Enhancements

Potential improvements for future versions:

1. **Unit Tests**: Add automated tests for each module
2. **Parallel Downloads**: Download from multiple sources simultaneously
3. **Checksum Verification**: Verify downloaded APK integrity
4. **Build Caching**: Smart caching to avoid rebuilding unchanged apps
5. **Plugin System**: Allow custom download sources
6. **Progress Indicators**: Show download/build progress
7. **Build Profiles**: Preset configurations for common use cases

## Contributing

When modifying the codebase:

1. Keep modules focused and single-purpose
2. Add logging at appropriate levels
3. Handle errors gracefully
4. Update this README for new functions
5. Test changes with various configurations
6. Maintain backward compatibility

## License

Same as parent project (Apache 2.0)
