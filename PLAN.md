# Implementation Plan: ReVanced Builder Python Refactor

## 1. Overview

This document outlines the strategic plan to **convert the ReVanced Builder codebase from Bash to Python** while integrating advanced features from community builders:
- [RookieEnough/Morphe-AutoBuilds](https://github.com/RookieEnough/Morphe-AutoBuilds)
- [X-Abhishek-X/ReVanced-Automated-Build-Scripts](https://github.com/X-Abhishek-X/ReVanced-Automated-Build-Scripts)
- [Sp3EdeR/revanced-auto-patcher](https://github.com/Sp3EdeR/revanced-auto-patcher)
- [peternmuller/revanced-morphe-builder](https://github.com/peternmuller/revanced-morphe-builder)
- [nikhilbadyal/docker-py-revanced](https://github.com/nikhilbadyal/docker-py-revanced)
- [Graywizard888/Enhancify](https://github.com/Graywizard888/Enhancify)
- [crimera/twitter-apk](https://github.com/crimera/twitter-apk)

### Goals
1. **Python-First Architecture**: Replace Bash orchestration with Python for better testability, cross-platform support, and maintainability
2. **Smart Build Automation**: Delta-based builds that skip unnecessary rebuilds
3. **Multi-Output Support**: APK (non-root), Magisk modules, and KernelSU modules
4. **Enhanced Notifications**: Telegram, Apprise, and GitHub release integration
5. **Performance Optimization**: Parallel builds, network acceleration, intelligent caching

---

## 2. Architecture Overview

### 2.1 Proposed Python Package Structure

```
scripts/
├── __init__.py                 # Package marker
├── cli.py                      # Main CLI entry point
├── builder/
│   ├── __init__.py
│   ├── config.py               # TOML/JSON config parsing (replace config.sh)
│   ├── downloader.py           # Multi-source APK downloading (replace download.sh)
│   ├── patcher.py              # ReVanced CLI patching logic (replace patching.sh)
│   ├── module_gen.py           # Magisk/KernelSU module generation
│   ├── version_tracker.py      # Delta build detection (enhance existing)
│   ├── notifier.py             # Telegram & Apprise notifications
│   ├── arch_config.py          # Architecture matrix handling
│   └── cache.py                # Intelligent caching (enhance existing cache.sh)
├── utils/
│   ├── __init__.py
│   ├── network.py              # HTTP requests with retries (enhance network.sh)
│   ├── apk.py                  # APK operations (sign, align, merge splits)
│   ├── java.py                 # Java subprocess management
│   └── process.py              # Parallel job management
├── scrapers/
│   ├── __init__.py
│   ├── apkmirror.py            # APKMirror scraping (enhance existing)
│   ├── uptodown.py             # Uptodown scraping (enhance existing)
│   ├── apkpure.py              # APKPure scraping (enhance existing)
│   ├── aptoide.py             # Aptoide scraping (enhance existing)
│   └── apkmonk.py             # APKMonk scraping (enhance existing)
└── search/
    ├── __init__.py
    └── version_resolver.py     # Version detection and compatibility
```

### 2.2 Key Design Decisions

| Aspect | Decision | Rationale |
|--------|----------|-----------|
| **Config Format** | TOML (keep) | Already well-supported via tomllib in Python 3.11+ |
| **Async I/O** | asyncio + httpx | For concurrent downloads and API calls |
| **Parallel Jobs** | concurrent.futures.ProcessPoolExecutor | CPU-bound patching benefits from multiprocessing |
| **CLI Framework** | argparse (stdlib) | Lightweight, no extra dependencies |
| **Signing** | Subprocess to apksigner | Existing Java tooling, don't reinvent |
| **Caching** | SQLite + file TTL | Better than JSON for concurrent access |

---

## 3. Feature Integration

### 3.1 CLI Profiles & Multi-Patcher Support
*Source: nikhilbadyal/docker-py-revanced, X-Abhishek-X/ReVanced-Automated-Build-Scripts*

**Implementation:**
```python
@dataclass
class CLIProfile:
    """CLI argument compatibility profile."""
    name: str  # "revanced-cli", "revanced-cli-v6", "morphe-cli"
    list_patches_args: dict[str, str]  # Override map for list-patches
    patch_args: dict[str, str]         # Override map for patch command
    
    # Built-in profiles
    REVANCED_CLI_V5 = CLIProfile("revanced-cli", {...})
    REVANCED_CLI_V6 = CLIProfile("revanced-cli-v6", {...})  
    MORPHE_CLI = CLIProfile("morphe-cli", {...})
```

**Config Schema (TOML):**
```toml
[global]
cli-profile = "revanced-cli-v6"  # or "auto" to detect

[YouTube]
# Multi-source patching support
patches-source = ["ReVanced/revanced-patches", "indrastorm/Dropped-patches"]

# CLI argument overrides
[YouTube.cli-overrides]
PATCHES = "-b"  # v6 uses -b for integrations
RIP_LIB = "--rip-lib"
```

**Migration from Bash:**
- `scripts/lib/patching.sh:_build_patcher_args()` → `builder/patcher.py:build_cli_args()`
- `scripts/lib/patching.sh:patch_apk()` → `builder/patcher.py:patch_apk()`

### 3.2 Smart Delta Monitoring & Version Tracking
*Source: X-Abhishek-X/ReVanced-Automated-Build-Scripts, Sp3EdeR/revanced-auto-patcher*

**Implementation:**
```python
@dataclass
class BuildState:
    """Tracks version state for smart rebuild detection."""
    global_cli_version: str
    global_patches_version: str
    global_patches_source: str
    app_versions: dict[str, AppVersionState]  # app_key -> version info
    
@dataclass  
class AppVersionState:
    """Per-app version tracking."""
    patches_source: str
    cli_source: str
    version: str
    integrations_version: str | None

class VersionTracker:
    """Smart build detection - skips builds when nothing changed."""
    
    def needs_build(self, config: Config) -> tuple[bool, list[VersionDiff]]:
        """Compare current config against saved state."""
        
    def save_state(self, config: Config) -> None:
        """Persist build state after successful build."""
        
    def get_release_notes(self, changes: list[VersionDiff]) -> str:
        """Generate changelog from version changes."""
```

**GitHub Actions Integration:**
```yaml
- name: Check if build needed
  run: python -m scripts.builder.version_tracker check --config config.toml
  
- name: Build
  if: needs_build == 'true'
  run: python -m scripts.cli build --config config.toml
  
- name: Save state
  if: needs_build == 'true'  
  run: python -m scripts.builder.version_tracker save --config config.toml
```

**Migration from Bash:**
- `scripts/version_tracker.py` (existing) → Enhance with integrations tracking

### 3.3 Magisk & KernelSU Module Engine
*Source: peternmuller/revanced-morphe-builder*

**Implementation:**
```python
class ModuleGenerator:
    """Generates Magisk/KernelSU modules from patched APKs."""
    
    def generate(
        self,
        apk_path: Path,
        app_name: str,
        brand: str,
        version: str,
        module_type: ModuleType,  # MAGISK or KERNSU
    ) -> Path:
        """Create module zip at $BUILD_DIR/$app-$brand-$version.zip"""
        
    def _create_module_structure(self) -> tempfile.TemporaryDirectory:
        """Build standard module directory structure."""
        # META-INF/com/google/android/updater-script
        # META-INF/com/google/android/updater-script (binary)
        # system/app/<app>/<apk>
        # service.sh (for mounting)
        
    def _generate_service_sh(self, apk_path: Path) -> str:
        """Generate service.sh for APK mounting."""
        
    def _generate_module_prop(self, metadata: ModuleMetadata) -> str:
        """Generate module.prop with proper versioning."""
```

**Config Schema (TOML):**
```toml
[global]
build-mode = "both"  # "apk", "module", "both"

[YouTube.module]
# Optional module-specific patch overrides
excluded-patches = ["some-patch"]

[global.module-config]
# KernelSU-specific options
kernelsu = true
```

**Migration from Bash:**
- New file `builder/module_gen.py` (no direct bash equivalent currently)

### 3.4 Advanced Split APK & Multi-Arch Handling
*Source: RookieEnough/Morphe-AutoBuilds, crimera/twitter-apk*

**Implementation:**
```python
class SplitAPKHandler:
    """Handles XAPK, APKM, and split APK merging."""
    
    def merge_splits(self, bundle_path: Path, output_apk: Path) -> bool:
        """Merge split APK bundle into single APK using APKEditor."""
        
    def extract_splits(self, apk_path: Path) -> list[Path]:
        """Extract split APKs from bundle."""
        
    def detect_bundle_type(self, file_path: Path) -> BundleType:
        """Detect if file is XAPK, APKM, or regular APK."""
        # Check file extension and MIME type
        
class ArchitectureMatrix:
    """Manages per-app architecture configurations."""
    
    # From RookieEnough/Morphe-AutoBuilds arch-config.json
    DEFAULT_MATRIX = {
        "youtube": ["arm64-v8a", "armeabi-v7a", "universal"],
        "youtube-music": ["arm64-v8a", "armeabi-v7a"],
        "reddit": ["universal"],
        "twitter": ["arm64-v8a"],
        "tiktok": ["universal"],
        "spotify": ["universal"],
    }
```

**Config Schema (TOML):**
```toml
[YouTube]
# Override architecture matrix
arch = ["arm64-v8a", "armeabi-v7a", "universal"]

[Twitter]
arch = ["arm64-v8a"]  # crimera/piko only supports arm64
```

### 3.5 Notification System
*Source: nikhilbadyal/docker-py-revanced*

**Implementation:**
```python
class NotifierFactory:
    """Create notifier instances based on configuration."""
    
    def create(self, config: NotificationConfig) -> Notifier:
        match config.provider:
            case "telegram": return TelegramNotifier(...)
            case "apprise": return AppriseNotifier(...)
            case "github": return GitHubReleaseNotifier(...)
            case _: return NullNotifier()

@dataclass
class BuildNotification:
    """Structured build notification payload."""
    app_name: str
    brand: str
    version: str
    arch: str
    output_path: Path
    changelog: str
    download_url: str | None  # For GitHub releases

class TelegramNotifier:
    """Telegram Bot API notifications."""
    
    async def send(self, notification: BuildNotification) -> bool:
        """Send build complete notification with screenshot/changelog."""
        
class AppriseNotifier:
    """Universal notification via Apprise library."""
    
    def send(self, notification: BuildNotification) -> bool:
        """Send to Discord, Matrix, Slack, etc. via Apprise."""
```

**Config Schema (TOML):**
```toml
[notifications]
provider = "telegram"  # telegram, apprise, github, none

[notifications.telegram]
token = "ENV:TELEGRAM_BOT_TOKEN"
chat-id = "ENV:TELEGRAM_CHAT_ID"

[notifications.apprise]
url = "ENV:APPRISE_URL"  # e.g., "tgram://bot-token/chat-id"

[notifications.github]
repository = "owner/repo"  # Auto-create release

[notifications.discord]
webhook = "ENV:DISCORD_WEBHOOK"
```

### 3.6 Network Acceleration & Resource Optimization
*Source: Graywizard888/Enhancify, RookieEnough/Morphe-AutoBuilds*

**Implementation:**
```python
class DownloadManager:
    """Multi-source download with failover and acceleration."""
    
    def __init__(
        self,
        use_aria2c: bool = False,
        max_workers: int = 4,
        retries: int = 4,
    ):
        self.use_aria2c = use_aria2c
        self.session = httpx.AsyncClient(timeout=300)
        
    async def download_with_fallback(
        self,
        sources: list[DownloadSource],
        output_path: Path,
    ) -> bool:
        """Try multiple sources in order until success."""
        
    async def download_with_aria2(
        self,
        urls: list[str],
        output_path: Path,
    ) -> bool:
        """Multi-threaded download via aria2c."""

class AAPT2Manager:
    """Dynamic AAPT2 fetching with caching."""
    
    # From Graywizard888/Enhancify
    SOURCES = [
        "Graywizard888/Custom-Enhancify-aapt2-binary",
        "ReVanced-Extended-Organization/AAPT2",
    ]
    
    async def get_aapt2(self, arch: str) -> Path:
        """Get AAPT2 binary, cached for 7 days."""
        
    def optimize_apk(
        self,
        apk_path: Path,
        output_path: Path,
        languages: list[str] = ["en"],
        densities: list[str] = ["xxhdpi"],
        arch: str = "arm64-v8a",
    ) -> bool:
        """Apply AAPT2 optimizations to reduce APK size."""
```

**Config Schema (TOML):**
```toml
[global]
# Network optimization
use-aria2c = false  # Enable for faster downloads
max-workers = 4

# AAPT2 optimization
enable-aapt2-optimize = true
aapt2-source = "Graywizard888/Custom-Enhancify-aapt2-binary"

# Resource stripping
riplib = true
```

### 3.7 Obtainium Metadata Generation
*Source: peternmuller/revanced-morphe-builder*

**Implementation:**
```python
class ObtainiumExporter:
    """Export app configs for Obtainium package manager."""
    
    def generate(
        self,
        apps: list[AppConfig],
        output_dir: Path,
    ) -> dict[str, ObtainiumApp]:
        """Generate Obtainium-compatible app definitions."""
        
@dataclass 
class ObtainiumApp:
    """Obtainium app configuration."""
    name: str
    package_name: str
    github_artifact_config: GitHubArtifactConfig
    additional_rules: list[AdditionalFilterRule]

@dataclass
class GitHubArtifactConfig:
    """GitHub release artifact matching rules."""
    repo: str
    version_regex: str  # e.g., "youtube-revanced-v(.*)"
    artifact_regex: str  # e.g., "youtube-revanced-(.*)-arm64-v8a.apk"
```

---

## 4. Configuration Schema (Enhanced)

```toml
# =============================================================================
# ReVanced Builder Configuration (Unified)
# =============================================================================

[global]
# Build modes: apk, module, both
build-mode = "both"

# Parallel build jobs (0 = auto-detect)
parallel-jobs = 0

# CLI Profile (auto, revanced-cli-v5, revanced-cli-v6, morphe-cli)
cli-profile = "auto"

# Version settings
patches-version = "latest"
cli-version = "latest"
version = "auto"

# Patch sources (supports multiple)
patches-source = "ReVanced/revanced-patches"

# Integrations
remove-rv-integrations-checks = true

# Resource optimization
riplib = true
compression-level = 9

# Architecture
arch = "arm64-v8a"  # or ["arm64-v8a", "armeabi-v7a", "universal"]

# AAPT2 optimization
enable-aapt2-optimize = true
aapt2-source = "Graywizard888/Custom-Enhancify-aapt2-binary"
use-custom-aapt2 = true

# Network
use-aria2c = false
max-workers = 4

[notifications]
provider = "telegram"  # telegram, apprise, github, none

[notifications.telegram]
token = "ENV:TELEGRAM_BOT_TOKEN"
chat-id = "ENV:TELEGRAM_CHAT_ID"

[notifications.apprise]
url = "ENV:APPRISE_URL"

# =============================================================================
# App Configurations
# =============================================================================

[YouTube]
enabled = true
app-name = "YouTube"
rv-brand = "ReVanced"
version = "auto"

# Multi-source patching
patches-source = ["ReVanced/revanced-patches", "indrastorm/Dropped-patches"]

# CLI overrides (optional)
[YouTube.cli-overrides]
PATCHES = "-b"

# Patch configuration
excluded-patches = ["'Enable debug logging'"]
patcher-args = [
    "-e", "Custom branding icon for YouTube",
    "-OappIcon=mnt",
]

# Download sources (tried in order)
apkmirror-dlurl = "https://apkmirror.com/apk/google-inc/youtube"
uptodown-dlurl = "https://youtube.en.uptodown.com/android"
archive-dlurl = "https://archive.org/download/jhc-apks/apks/com.google.android.youtube"

# Architecture override
arch = ["arm64-v8a", "armeabi-v7a", "universal"]

# APK output name
output-name = "{app}-{brand}-v{version}-{arch}"

[YouTube.module]
# Module-specific exclusions
excluded-patches = ["another-module-only-patch"]

[YouTube.morphe]
# Alternative: build with Morphe instead
patches-source = "MorpheApp/morphe-patches"
cli-source = "MorpheApp/morphe-cli"
rv-brand = "Morphe"

[YouTube.RVX]
# Alternative: build with ReVanced Extended
patches-source = "anddea/revanced-patches"
cli-source = "inotia00/revanced-cli"
rv-brand = "RVX"
version = "20.21.37"
```

---

## 5. Implementation Roadmap

### Phase 1: Core Python Foundation (Week 1)
**Goal:** Establish Python infrastructure with parity to existing Bash

| Task | Files | Dependencies |
|------|-------|--------------|
| Create package structure | `scripts/__init__.py`, `scripts/cli.py` | - |
| Config parser | `scripts/builder/config.py` | tomllib, tomli-w |
| Network utilities | `scripts/utils/network.py` | httpx, anyio |
| Java subprocess wrapper | `scripts/utils/java.py` | - |
| APK operations | `scripts/utils/apk.py` | zipalign, apksigner (external) |
| Basic CLI entry point | `scripts/cli.py` | argparse |

**Deliverables:**
- `python -m scripts.cli --help` works
- Config loading produces equivalent output to current `toml_get_*` functions
- Downloads work with existing source URLs

### Phase 2: Patching Engine (Week 2)
**Goal:** Replace `patching.sh` and `app_processor.sh` with Python equivalents

| Task | Files | Dependencies |
|------|-------|--------------|
| CLI profile system | `scripts/builder/cli_profiles.py` | - |
| ReVanced CLI wrapper | `scripts/builder/patcher.py` | java.py |
| Version resolver | `scripts/search/version_resolver.py` | - |
| App processor orchestrator | `scripts/builder/app_processor.py` | config.py, patcher.py |
| Parallel job execution | `scripts/utils/process.py` | concurrent.futures |

**Deliverables:**
- `python -m scripts.cli build --config config.toml` produces identical APKs
- Multi-source patching works (multiple `-p` flags)
- CLI profile switching works for v4/v5/v6/Morphe

### Phase 3: Module Generation (Week 3)
**Goal:** Add Magisk/KernelSU module support from `peternmuller/revanced-morphe-builder`

| Task | Files | Dependencies |
|------|-------|--------------|
| Module structure generator | `scripts/builder/module_gen.py` | zipfile |
| service.sh generation | `scripts/builder/module_gen.py` | - |
| module.prop generator | `scripts/builder/module_gen.py` | - |
| KernelSU support | `scripts/builder/module_gen.py` | - |
| build-mode config | `scripts/builder/config.py` | - |

**Deliverables:**
- `--build-mode both` produces APK and module zip
- Modules mount correctly on Magisk/KernelSU
- rvmm-zygisk-mount integration support

### Phase 4: Smart Builds & Notifications (Week 4)
**Goal:** Add delta detection and notifications

| Task | Files | Dependencies |
|------|-------|--------------|
| Enhanced version tracker | `scripts/builder/version_tracker.py` | orjson, github API |
| Change detection | `scripts/builder/version_tracker.py` | - |
| Telegram notifier | `scripts/builder/notifier.py` | httpx |
| Apprise notifier | `scripts/builder/notifier.py` | apprise |
| GitHub release integration | `scripts/builder/notifier.py` | ghapi |

**Deliverables:**
- `version_tracker.py check` skips builds when nothing changed
- Build notifications sent on completion
- GitHub releases auto-created with changelog

### Phase 5: Polish & Performance (Week 5)
**Goal:** Performance optimization and edge cases

| Task | Files | Dependencies |
|------|-------|--------------|
| Aria2c integration | `scripts/utils/network.py` | aria2c (external) |
| AAPT2 optimization | `scripts/utils/apk.py` | aapt2 (external) |
| Split APK handling | `scripts/utils/apk.py` | APKEditor (external) |
| Comprehensive tests | `tests/` | pytest, pytest-cov |
| Documentation | `docs/` | mkdocs |

**Deliverables:**
- `use-aria2c = true` enables multi-threaded downloads
- Split APK/XAPK merging works
- 80%+ test coverage
- Full documentation

---

## 6. Migration Strategy

### 6.1 Parallel Operation
Keep existing Bash scripts working while Python is developed:
1. New Python CLI in `scripts/cli.py`
2. Bash `build.sh` wraps Python: `python -m scripts.cli "$@"`
3. Both produce identical output during transition

### 6.2 Incremental Replacement Order
1. **Phase 1:** Config parsing (Python replaces Bash TOML parsing)
2. **Phase 2:** Downloads and patching (core workflow)
3. **Phase 3:** Module generation (new capability)
4. **Phase 4:** Version tracking (enhancement)
5. **Phase 5:** Notifications (new capability)

### 6.3 Backwards Compatibility
- Config.toml format stays compatible
- Existing build.sh continues to work
- Gradual feature flag migration: `--python-build` opt-in

---

## 7. Testing Strategy

### 7.1 Unit Tests
```bash
# Python tests
python -m pytest tests/test_*.py -v

# Bash lint
bash -n scripts/lib/*.sh
shellcheck scripts/lib/*.sh
```

### 7.2 Integration Tests
```bash
# Full build test
python -m scripts.cli build --config config.toml

# Compare output with Bash build
diff build/bash/*.apk build/python/*.apk
```

### 7.3 Test Coverage Targets
| Component | Target |
|-----------|--------|
| config.py | 90% |
| patcher.py | 85% |
| downloader.py | 80% |
| version_tracker.py | 90% |
| Overall | 80% |

---

## 8. Dependencies

### Python (pyproject.toml)
```toml
[project]
requires-python = ">=3.11"
dependencies = [
    "selectolax>=0.3.21",      # HTML parsing (existing)
    "orjson>=3.10.0",           # JSON (existing)
    "httpx>=0.28.0",           # HTTP client
    "tomli-w>=1.1.0",          # TOML writing
    "apprise>=1.9.0",           # Notifications
]

[dependency-groups]
dev = [
    "pytest>=9.0.0",
    "pytest-cov>=6.0.0",
    "pytest-asyncio>=0.25.0",
    "mypy>=1.15.0",
    "ruff>=0.9.0",
    "hypothesis>=6.100.0",
]
```

### External Requirements
- Java 21+ (for ReVanced CLI, apksigner)
- `zipalign` (Android SDK)
- `apksigner` (Android SDK)
- `aria2c` (optional, for accelerated downloads)
- `APKEditor` V1.4.2+ (for split APK merging)

---

## 9. File Manifest

### New Python Files
```
scripts/
├── __init__.py
├── cli.py                          # Main CLI
├── builder/
│   ├── __init__.py
│   ├── config.py                   # Config parsing
│   ├── patcher.py                  # ReVanced patching
│   ├── module_gen.py               # Magisk/KernelSU modules
│   ├── version_tracker.py          # Delta detection
│   ├── notifier.py                 # Notifications
│   ├── app_processor.py            # Build orchestration
│   └── cli_profiles.py             # CLI argument profiles
├── utils/
│   ├── __init__.py
│   ├── network.py                  # HTTP with retries
│   ├── apk.py                      # APK operations
│   ├── java.py                     # Java subprocess
│   └── process.py                  # Parallel jobs
├── scrapers/
│   ├── __init__.py
│   ├── base.py                     # Base scraper class
│   ├── apkmirror.py                # APKMirror
│   ├── uptodown.py                 # Uptodown
│   ├── apkpure.py                  # APKPure
│   ├── aptoide.py                  # Aptoide
│   └── apkmonk.py                  # APKMonk
└── search/
    ├── __init__.py
    └── version_resolver.py         # Version detection
```

### Files to Deprecate (Bash → Python)
| Bash File | Python Replacement | Status |
|-----------|-------------------|--------|
| `build.sh` | `cli.py` | To be rewritten |
| `scripts/lib/config.sh` | `builder/config.py` | To be rewritten |
| `scripts/lib/download.sh` | `scrapers/*.py` | To be rewritten |
| `scripts/lib/patching.sh` | `builder/patcher.py` | To be rewritten |
| `scripts/lib/app_processor.sh` | `builder/app_processor.py` | To be rewritten |
| `scripts/lib/network.sh` | `utils/network.py` | To be enhanced |
| `scripts/lib/cache.sh` | `utils/cache.py` | To be rewritten |
| `scripts/version_tracker.py` | `builder/version_tracker.py` | To be enhanced |

### Files to Keep
- `scripts/apkmirror_search.py` → Integrate into `scrapers/apkmirror.py`
- `scripts/apkpure_search.py` → Integrate into `scrapers/apkpure.py`
- `scripts/aptoide_search.py` → Integrate into `scrapers/aptoide.py`
- `scripts/apkmonk_search.py` → Integrate into `scrapers/apkmonk.py`
- `scripts/html_parser.py` → Keep as utility
- `scripts/aapt2-optimize.sh` → Convert to `utils/apk.py`
- `utils.sh` → Deprecate (sources Python instead)

---

## 10. TODO.md Items Incorporated

From the original TODO.md:

- ✅ **peternmuller/revanced-morphe-builder**: Module generation (Phase 3)
- ✅ **nikhilbadyal/docker-py-revanced**: CLI profiles, notifications, multi-patching (Phase 1-4)
- ✅ **crimera/twitter-apk**: Split APK handling (Phase 5)
- ✅ **X-Abhishek-X/ReVanced-Automated-Build-Scripts**: Delta builds, version tracking (Phase 4)
- ✅ **RookieEnough/Morphe-AutoBuilds**: Architecture matrix, multi-source (Phase 1-2)
- ✅ **Sp3EdeR/revanced-auto-patcher**: Simple patching interface, patch options (Phase 2)
- ✅ **Graywizard888/Enhancify**: Aria2c, AAPT2 optimizations (Phase 5)

---

## 11. Success Metrics

| Metric | Target |
|--------|--------|
| Build parity | 100% - Python and Bash produce identical APKs |
| Test coverage | ≥80% |
| Build time | ≤50% of current (with parallelization) |
| Config file size | No increase |
| Learning curve | Existing configs work without modification |
