# GitHub Copilot Instructions

This file provides concise instructions for GitHub Copilot when working with the ReVanced Builder codebase.

## Project Type

**ReVanced Builder**: Bash-based automated APK patching system for ReVanced/RVX applications.

**Tech Stack**: Bash 4.0+, Python 3.11+, TOML configs, Make, GitHub Actions CI/CD

## Critical Rules

### Always Follow These

1. **Module Loading**: ALWAYS `source utils.sh` to load all library modules. NEVER source individual `scripts/lib/` files directly.

2. **Logging**: Use logging functions from `scripts/lib/logger.sh`:
   - `log_debug`, `log_info`, `log_warn` for messages
   - `epr` for non-fatal errors
   - `abort` for fatal errors (exits with code 1)
   - NEVER use `echo` or `printf` for user-facing messages

3. **Bash Best Practices**:
   - Header: `#!/usr/bin/env bash` + `set -euo pipefail`
   - Tests: Use `[[ ... ]]` NOT `[ ... ]`
   - Always quote variables: `"${var}"`
   - Use `local` for function-scoped variables
   - Functions: `snake_case` (public) or `_snake_case` (private)
   - Variables: `UPPER_CASE` (global), `lower_case` (local)

4. **Security**:
   - Never use `eval`
   - Never commit secrets
   - Always verify APK signatures before patching
   - Sign APKs with v1+v2 only (v3/v4 disabled)

5. **Performance**:
   - Use caching for HTTP requests and downloads
   - Keep algorithmic complexity O(n) or better
   - Prefer native Python/Bash over subprocess spawning
   - Use parallel operations when possible

## Code Style

### Bash

```bash
#!/usr/bin/env bash
set -euo pipefail

# Good: Quoted expansion, local vars, [[ ]] test
function process_app() {
    local app_name=$1
    local version=$2

    if [[ -z ${app_name} ]]; then
        abort "App name required"
    fi

    log_info "Processing ${app_name}"
}

# Avoid: Unquoted vars, [ ] tests, global vars, eval
```

### Python

```python
def parse_html(content: str, selector: str) -> list[str]:
    """Extract text using CSS selector.

    Args:
        content: HTML content
        selector: CSS selector pattern

    Returns:
        List of extracted strings
    """
    # Use type hints, docstrings, PEP 8
```

## Common Patterns

### Configuration Access

```bash
# Always load utils.sh first
source utils.sh

# Prepare and access config
toml_prep "config.toml"
local value=$(toml_get "table" "key")
```

### Network Requests with Retry

```bash
# Automatic exponential backoff (5 retries)
local response=$(req "https://api.example.com/data")
```

### Caching

```bash
if is_cached "resource-key"; then
    local path=$(get_cached_path "resource-key")
else
    download_resource "output.bin"
    cache_resource "resource-key" "output.bin"
fi
```

### Error Handling

```bash
# Fatal error (exits)
abort "Build failed: incompatible version"

# Non-fatal error (continues)
epr "Warning: optimization skipped"

# Check exit codes
if ! some_command; then
    log_warn "Command failed but continuing"
fi
```

## Architecture Overview

### Module Structure

```
utils.sh (loader) → sources all modules in order:
  scripts/lib/logger.sh    - Logging
  scripts/lib/helpers.sh   - Utilities
  scripts/lib/config.sh    - TOML parsing
  scripts/lib/network.sh   - HTTP with retry
  scripts/lib/cache.sh     - Build caching
  scripts/lib/prebuilts.sh - CLI/patches downloads
  scripts/lib/download.sh  - APK downloads
  scripts/lib/patching.sh  - Patching orchestration
  scripts/lib/checks.sh    - Prerequisites
```

### Build Pipeline

```
Check Prerequisites → Load Config → Download CLI+Patches
  ↓
For each app:
  Detect Version → Download APK → Verify Signature
  Apply Patches → Optimize → Sign → Output
```

### Multi-Source Patches

System supports multiple patch sources automatically:

```toml
patches-source = ["org1/patches", "org2/patches"]
```

- Union version detection across all sources
- Applies with multiple `-p` flags to RevancedCLI
- Last patch wins on conflicts (based on array order)

### Download Fallback

APK downloads try sources in order:
1. APKMirror (primary)
2. Uptodown (secondary, XAPK support)
3. Archive.org (tertiary, historical)

## Key Functions to Know

### scripts/lib/helpers.sh
- `get_highest_ver()` - Get highest version from stdin
- `scrape_text(selector)` - Extract text from HTML
- `scrape_attr(selector, attr)` - Extract HTML attribute

### scripts/lib/patching.sh
- `build_rv(app_table)` - Main build orchestration
- `patch_apk(...)` - Apply patches to APK
- `check_sig(apk, pkg)` - Verify APK signature

### scripts/lib/download.sh
- `dl_apkmirror(url, ver, output, arch, dpi)`
- `dl_uptodown(url, ver, output)`
- `dl_archive(url, ver, output)`

## Environment Variables

### Required for Building
- `KEYSTORE_PASSWORD` - Keystore password
- `KEYSTORE_ENTRY_PASSWORD` - Key entry password

### Optional
- `LOG_LEVEL` - 0=DEBUG, 1=INFO, 2=WARN, 3=ERROR
- `MAX_RETRIES` - Network retry attempts (default: 4)
- `GITHUB_TOKEN` - For authenticated API requests

## Linting & Testing

**Before committing:**
```bash
make lint     # Check all files
make format   # Auto-fix issues
make test-syntax  # Verify Bash syntax
```

**Linters by file type:**
- Shell: ShellCheck, shfmt, shellharden
- Python: Ruff
- YAML: yamllint, yamlfmt
- TOML: taplo
- JSON/HTML/JS/TS/CSS: Biome

## File Naming

- Bash scripts: `kebab-case.sh`
- Python scripts: `snake_case.py`
- Config files: `.lowercase` or `UPPERCASE.md`
- Test files: `test_*.sh`

## Git Workflow

**Branches:**
- Features: `feature/description`
- Fixes: `fix/description`
- AI agents: `claude/description-<session-id>`

**Commits:**
- Run linters before committing
- Use descriptive messages
- Include session URL in commit body

## Common Tasks

### Adding Download Source

1. Add functions to `scripts/lib/download.sh`:
   - `get_source_resp()`, `get_source_vers()`, `dl_source()`
2. Update `_download_stock_apk()` in `scripts/lib/patching.sh`
3. Add config key to `config.toml`

### Adding Config Option

1. Add default in `build.sh:validate_config_value()`
2. Access via `toml_get()` in modules
3. Document in `CONFIG.md`

### Debugging

```bash
export LOG_LEVEL=0  # Enable debug logging
./build.sh config.toml 2>&1 | tee debug.log
```

## Quick Reference

### Preferred Tools
- `jq` for JSON parsing
- Python's `tomllib` for TOML
- `lxml`+`cssselect` for HTML parsing
- Modern tools: `fd` over `find`, `rg` over `grep` (when available)

### Avoid
- `eval` (security risk)
- Backticks (use `$(...)`)
- Unquoted expansions
- Piping curl to shell
- Nested loops for large datasets
- Spawning subprocesses in loops

### Python Dependencies
- Runtime: `lxml>=5.2.2`, `cssselect>=1.2.0`
- Dev: `ruff>=0.8.0`

### System Requirements
- Bash 4.0+
- Java 21+ (OpenJDK Temurin)
- Python 3.11+
- Tools: jq, zip, curl/wget

## Additional Resources

- **AGENTS.md** - Comprehensive guide for all AI assistants
- **README.md** - User documentation
- **CONFIG.md** - Configuration reference
- **LINTING.md** - Linting guide
- **.github/instructions/** - Detailed style guides

---

**Key Reminder**: Always `source utils.sh` to load modules. Never source individual `scripts/lib/` files.
