# Project Index: ReVanced Builder

**Generated:** 2026-01-13
**Project Type:** Bash-based APK Patching System
**Architecture:** Modular library system with central loader

---

## 📁 Project Structure

```
Revanced-auto/
├── bin/                    # Prebuilt binaries (arch-specific)
│   ├── aapt2/             # Android Asset Packaging Tool
│   ├── apksigner.jar      # APK signing
│   ├── dexlib2.jar        # DEX manipulation
│   └── paccer.jar         # Patch integrity checker
├── scripts/                # Automation scripts and libraries
│   ├── lib/               # Core library modules (2,512 LOC)
│   │   ├── logger.sh      # Multi-level logging
│   │   ├── helpers.sh     # Utilities & version comparison
│   │   ├── config.sh      # TOML/JSON parsing
│   │   ├── network.sh     # HTTP with retry logic
│   │   ├── cache.sh       # Build cache management
│   │   ├── prebuilts.sh   # ReVanced CLI/patches download
│   │   ├── download.sh    # APK downloads (APKMirror/Uptodown/Archive)
│   │   ├── patching.sh    # APK patching orchestration
│   │   └── checks.sh      # Environment validation
│   ├── html_parser.py     # Python HTML parser (replaces htmlq)
│   ├── toml_get.py        # Python TOML/JSON converter
│   ├── aapt2-optimize.sh
│   ├── changelog-generator.sh
│   ├── dependency-checker.sh
│   ├── generate_matrix.sh
│   ├── optimize-assets.sh
│   ├── release-manager.sh
│   └── unused-strings.sh
├── tests/                  # Test configurations
├── docs/                   # Documentation
├── conductor/              # Project management metadata
├── .github/                # CI/CD workflows
└── plans/                  # Future development plans
```

---

## 🚀 Entry Points

### Primary
- **build.sh** - Main build orchestrator
  - Syntax: `./build.sh <config.toml>`
  - Modes: Build all enabled apps, clean, cache management
  - Exit codes: 0 (success), 1 (error), 130 (interrupted)

### Utilities
- **utils.sh** - Central module loader (sources all scripts/lib/*.sh)
- **extras.sh** - CI/CD utilities (separate-config, combine-logs)
- **check-env.sh** - Environment prerequisite validation

### Testing
- **test-multi-source.sh** - Multi-source patch testing
- **test_checks.sh** - Environment checks testing

---

## 📦 Core Modules (scripts/lib/)

### Foundation Layer

#### **logger.sh**
- **Exports:** `log_debug`, `log_info`, `log_warn`, `epr`, `abort`, `pr`, `log`
- **Purpose:** Multi-level logging (DEBUG/INFO/WARN/ERROR)
- **Features:** Color-coded output, LOG_LEVEL control, build.md logging

#### **helpers.sh**
- **Exports:** `isoneof`, `get_highest_ver`, `get_patch_last_supported_ver`, `set_prebuilts`
- **Purpose:** Version comparison, validation utilities
- **Key:** Semantic version parsing, architecture detection

### Configuration Layer

#### **config.sh**
- **Exports:** `toml_prep`, `toml_get`, `toml_get_array_or_string`
- **Purpose:** TOML/JSON parsing via Python (tomllib)
- **Features:** Converts TOML → JSON, caches in `__TOML__` variable

### Network Layer

#### **network.sh**
- **Exports:** `req`, `dl_gh`, `gh_req`, HTTP request functions
- **Purpose:** HTTP requests with exponential backoff retry
- **Features:** 5 retries, 2s initial delay, connection timeout

#### **cache.sh**
- **Exports:** `cache_init`, `cache_get`, `cache_set`, `cache_stats`, `cache_cleanup`
- **Purpose:** Intelligent build cache with TTL & integrity validation
- **Features:** SQLite backend, automatic cleanup, size tracking

### Download Layer

#### **prebuilts.sh**
- **Exports:** `get_rv_prebuilts_multi`, `download_cli`, `download_patches`
- **Purpose:** ReVanced CLI & patches download management
- **Features:** Multi-source support, version resolution (latest/dev/specific)

#### **download.sh**
- **Exports:** `dl_apkmirror`, `dl_uptodown`, `dl_archive`, version detection
- **Purpose:** Stock APK downloads with fallback sources
- **Features:** XAPK support, split APK merging, signature verification

### Patching Layer

#### **patching.sh**
- **Exports:** `build_rv`, `patch_apk`, `merge_splits`, `check_sig`
- **Purpose:** APK patching orchestration
- **Features:** Multi-source patches, version auto-detection, optimization

#### **checks.sh**
- **Exports:** `check_prerequisites`, validation functions
- **Purpose:** Environment validation (Java 21+, jq, zip)

---

## 🔧 Configuration

### Primary Config
- **config.toml** - Main build configuration
  - Global settings (patches-source, CLI version, arch, etc.)
  - Per-app overrides ([YouTube-Extended], [Music-Extended], etc.)
  - Multi-source patch support (array or string)

### Test Configs
- **tests/config-multi-source-test.toml** - Multi-source testing
- **tests/config-single-source-test.toml** - Single-source testing

---

## 📚 Documentation

### User Documentation
- **README.md** - Quick start guide, features overview
- **CONFIG.md** - Configuration reference
- **CLAUDE.md** - AI assistant context & architecture
- **AGENTS.md** - Code style guide for AI agents
- **docs/FEATURES.md** - Detailed feature documentation
- **docs/README.md** - Extended documentation index

### Developer Documentation
- **conductor/** - Project management metadata
  - product.md - Product vision
  - tech-stack.md - Technology choices
  - workflow.md - Development workflow
  - code_styleguides/shell.md - Bash style guide

### Process Documentation
- **.github/WORKFLOWS.md** - CI/CD pipeline documentation
- **scripts/README.md** - Script usage documentation

---

## 🧪 Test Coverage

- **Unit tests:** 2 config files (multi-source, single-source)
- **Integration tests:** test-multi-source.sh, test_checks.sh
- **CI/CD validation:**
  - ShellCheck linting
  - Dependency checks
  - PR validation builds
  - Daily builds

---

## 🔗 Key Dependencies

### Runtime
- **Bash** 4.0+ - Shell interpreter
- **Java** 21+ - APK signing & patching
- **Python** 3.11+ - HTML parsing & TOML conversion
- **jq** - JSON parsing
- **zip** - APK manipulation
- **curl/wget** - HTTP downloads

### Python Dependencies
- **lxml** - HTML parsing library
- **cssselect** - CSS selector support

### Optional
- **optipng** - Asset optimization

### Prebuilt Binaries
- **apksigner.jar** - APK signing (v1+v2 only)
- **dexlib2.jar** - DEX manipulation
- **paccer.jar** - Patch validation
- **aapt2** - Resource optimization (arch: arm, arm64, x86_64)

### Python Utilities
- **html_parser.py** - HTML parsing with CSS selectors (lxml)
- **toml_get.py** - TOML config parsing (tomllib)

---

## 📝 Quick Start

### 1. Prerequisites Check
```bash
./check-env.sh
```

### 2. Configure Build
```bash
# Edit config.toml or use web-based generator
vim config.toml
```

### 3. Build APKs
```bash
# Build all enabled apps
./build.sh config.toml

# Enable debug logging
export LOG_LEVEL=0
./build.sh config.toml
```

### 4. Clean Build Artifacts
```bash
./build.sh clean
```

---

## 🏗️ Build Pipeline Flow

```
Prerequisites Check (Java 21+, jq, zip)
  ↓
Load config.toml (TOML → JSON via Python toml_get.py)
  ↓
Download ReVanced CLI + Patches (multi-source support)
  ├── CLI: shared across all sources
  └── Patches: one per source (temp/<org>-rv/)
  ↓
For each enabled app:
  ├── Detect version (auto = union of compatible versions)
  ├── Download stock APK (APKMirror → Uptodown → Archive)
  ├── Verify signature (sig.txt)
  ├── Apply patches (CLI with multiple -p flags)
  ├── Optimize (aapt2, riplib, zipalign)
  └── Sign (v1+v2 only)
  ↓
Output → build/ directory
```

---

## 🔒 Security Features

- **Signature Verification:** Pre-patch APK signature validation
- **APK Signing:** v1+v2 schemes (v3/v4 disabled for compatibility)
- **Input Validation:** Sanitized config values
- **No Eval:** No dynamic code execution
- **CI/CD Security:** Keystore secrets, fork isolation

---

## 📊 Token Efficiency Stats

**Index Size:** ~3.5KB (human-readable)
**Estimated Tokens:** ~1,200 tokens
**Full Codebase:** ~58,000 tokens (22 shell scripts, 2,512 LOC)
**Token Savings:** 98% reduction

**Use Cases:**
- Quick architecture overview
- Module dependency understanding
- Entry point identification
- Configuration reference
- Build pipeline comprehension

---

## 🚦 CI/CD Workflows

### GitHub Actions
- **build.yml** - Standard build workflow
- **build-daily.yml** - Scheduled daily builds
- **build-manual.yml** - Manual dispatch builds
- **build-pr.yml** - PR validation (no publish)
- **ci.yml** - Continuous integration checks
- **dependency-check.yml** - Dependency monitoring
- **shellcheck.yml** - Shell script linting

---

## 📈 Recent Activity

**Last Refactor:** Phase 2 complete (Logic Centralization)
**Active Track:** refactor_20260113
**Recent Changes:**
- Asset path updates
- Deprecated function removal
- Config parsing improvements

---

## 🎯 Key Architectural Patterns

### 1. Modular Library System
- Central loader (utils.sh)
- Dependency-ordered sourcing
- No circular dependencies

### 2. Multi-Source Patch Support
- Union version detection
- CLI shared, patches per-source
- Automatic fallback & conflict resolution

### 3. Download Fallback Chain
- APKMirror (primary) → Uptodown (secondary) → Archive (tertiary)
- Automatic source switching on failure

### 4. Retry Logic with Exponential Backoff
- 5 attempts, 2s initial delay
- Doubles each retry
- All network operations protected

### 5. Cache-First Strategy
- SQLite-based cache
- TTL & integrity validation
- Automatic cleanup

---

**End of Index**

*For detailed information on any component, consult the source files or relevant documentation in docs/*
