# Implementation Plan: ReVanced Builder Integration

This document outlines the strategic plan to integrate advanced features and logic from community ReVanced/Morphe builders into this repository.

## 1. Objectives
- **Universal Compatibility**: Support multiple CLI versions (v4, v5, v6) and patcher sources (ReVanced, Morphe, RVX).
- **Flexible Output**: Support both non-root APKs and root-ready Magisk/KernelSU modules.
- **Smart Automation**: Implement delta-based builds and comprehensive notification systems.
- **Performance**: Optimize build times through parallelization, network acceleration, and efficient resource handling.

## 2. Feature Integration Strategy

### A. Magisk & KernelSU Module Engine
*Source: peternmuller/revanced-morphe-builder*
- **Action**: Implement a new library `scripts/lib/module_gen.sh` to handle module creation.
- **Logic**: Package patched APKs into a Magisk-compatible structure with `service.sh` for mounting. Support `rvmm-zygisk-mount` for improved compatibility.
- **Config**: Add `build-mode = "module"` or `"both"` in `config.toml`.

### B. CLI Profiles & Multi-Patcher Support
*Source: nikhilbadyal/docker-py-revanced*
- **Action**: Update `scripts/lib/patching.sh` to support "CLI Profiles".
- **Logic**: Define argument maps for different CLI versions (e.g., v6 requires `-b` for integrations, Morphe CLI uses different flags). Allow multiple `-p` flags to merge patches from different sources (e.g., official + indrastorm).
- **Config**: `cli-profile = "v6"` in `config.toml`.

### C. Smart Delta Monitoring
*Source: X-Abhishek-X/ReVanced-Automated-Build-Scripts*
- **Action**: Extend `scripts/version_tracker.py` (and its default `.github/last_built_versions.json` state) and, if needed, add a thin Bash wrapper in `scripts/lib` to integrate it with `build.sh`.
- **Logic**: Reuse and, if necessary, expand the existing JSON state to track the last built versions of patches, integrations, and target apps. Before building, query GitHub APIs for the latest versions and skip the build if no relevant changes are detected.
- **Efficiency**: Significantly reduces GitHub Actions runner usage.

### D. Advanced Split APK & Multi-Arch Handling
*Source: RookieEnough/Morphe-AutoBuilds, crimera/twitter-apk*
- **Action**: Enhance `merge_splits` in `scripts/lib/patching.sh`.
- **Logic**: Use `APKEditor` more robustly to handle XAPK and APKM formats. Expand the architecture matrix to consistently generate `arm64-v8a`, `armeabi-v7a`, and `universal` variants.

### E. Notification System (Telegram & Apprise)
*Source: nikhilbadyal/docker-py-revanced*
- **Action**: Create `scripts/lib/notifications.sh`.
- **Logic**: Integrate Telegram Bot API and Apprise for universal notifications (Discord, Matrix, etc.). Send build summaries, changelogs, and download links upon successful completion.

### F. Network & Resource Acceleration
*Source: Graywizard888/Enhancify*
- **Action**: Update `scripts/lib/network.sh`.
- **Logic**: Optional integration of `aria2c` for multi-threaded downloads. Improve local caching of tools like `aapt2` and `apksigner`.

## 3. Implementation Roadmap

### Phase 1: Core Engine & Multi-Source (Week 1)
- Refactor `patching.sh` for CLI Profiles and per-CLI argument maps.
- Formalize and document multi-patcher JAR support (already available via multiple `-p` flags and array `patches-source`) and add tests.
- Expand `config.toml` schema for CLI profiles, notification settings, and module output.

### Phase 2: Output Expansion (Week 2)
- Implement Magisk/KernelSU module generation.
- Update `build.sh` to handle multiple output formats.
- Add Obtainium metadata generation.

### Phase 3: Automation & Notifications (Week 3)
- Integrate and wire `scripts/version_tracker.py` into the build workflow for delta-based builds.
- Integrate Telegram and Apprise notification systems.
- Automate release management (cleaning old releases).

### Phase 4: Performance & Refinement (Week 4)
- Network acceleration with `aria2c`.
- Refine and extend existing AAPT2 optimizations (`scripts/aapt2-optimize.sh`, dynamic AAPT2 fetch/caching in `set_prebuilts`).
- Comprehensive unit testing and documentation updates.

## 4. Configuration Schema Updates (Proposed)

```toml
[global]
build-mode = "apk" # apk, module, both
notification-provider = "telegram" # telegram, apprise, none
cli-profile = "auto" # auto, v4, v5, v6, morphe

[notifications.telegram]
token = "ENV:TELEGRAM_TOKEN"
chat-id = "ENV:TELEGRAM_CHAT_ID"

[YouTube]
# Support multiple patch sources
patches-source = ["ReVanced/revanced-patches", "indrastorm/Dropped-patches"]
```
