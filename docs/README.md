# ReVanced Builder Documentation

Welcome to the ReVanced Builder documentation and tools directory.

## 📁 Contents

### Configuration Generator
**Location**: [`index.html`](./index.html)

A web-based tool for creating `config.toml` files without manual editing.

**Features**:
- Interactive form-based interface
- Live TOML preview
- **Visual patch selector** - Browse and select patches like ReVanced Manager
- Global and per-app settings
- Download or copy generated configuration
- Example configurations
- Patch search and filtering
- Auto-fetch patches from GitHub repositories

**Access**: [Open Configuration Generator](./index.html)

## 🚀 Quick Start

### Using the Configuration Generator

1. Open [`index.html`](./index.html) in your browser
2. Configure global settings (parallel jobs, compression, etc.)
3. Add applications using the "+ Add Application" button
4. Fill in app details (name, version, download URLs)
5. **Click "Browse & Select Patches"** to visually select patches (like ReVanced Manager)
   - Searches and filters available patches
   - Select/deselect individual patches with checkboxes
   - Auto-generates excluded-patches configuration
6. See live preview on the right
7. Download or copy the generated `config.toml`

### Configuration Options

**Global Settings**:
- `parallel-jobs` - Number of simultaneous builds
- `compression-level` - ZIP compression (0-9)
- `patches-source` - Default GitHub repo for patches
- `cli-source` - ReVanced CLI source
- `arch` - Default architecture (arm64-v8a, armeabi-v7a, both)
- `riplib` - Strip unnecessary libraries
- `enable-aapt2-optimize` - Resource optimization

**Per-App Settings**:
- `enabled` - Enable/disable app building
- `app-name` - Display name
- `version` - auto, latest, or specific version
- `patches-source` - Override patches source
- Download URLs (APKMirror, Uptodown, Archive.org)
- **Patch Selection** - Visual patch browser (fetches from GitHub)
  - Search and filter patches
  - Select/deselect with checkboxes
  - Auto-detects compatible patches
- `excluded-patches` - Patches to skip (manual or auto-generated)
- `included-patches` - Exclusive patch list

## 📖 Additional Documentation

- [Main README](../README.md) - Project overview
- [Configuration Reference](../CONFIG.md) - Detailed config documentation
- [Workflows](../.github/WORKFLOWS.md) - CI/CD documentation
- [Architecture](../CLAUDE.md) - Technical architecture

## 🤝 Contributing

When adding documentation:
1. Keep it concise and actionable
2. Include code examples
3. Update this index
4. Test all links

## 🔗 External Links

- [ReVanced Project](https://github.com/ReVanced)
- [ReVanced Extended (RVX)](https://github.com/inotia00/revanced-patches)
- [GitHub Pages Documentation](https://docs.github.com/en/pages)

---

**Generated with**: ReVanced Builder
**Last Updated**: 2026-01-21
