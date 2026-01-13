# ReVanced Builder

[![Daily Build](https://github.com/YOUR-USERNAME/Revanced-auto/actions/workflows/build-daily.yml/badge.svg)](https://github.com/YOUR-USERNAME/Revanced-auto/actions/workflows/build-daily.yml)
[![PR Validation](https://github.com/YOUR-USERNAME/Revanced-auto/actions/workflows/build-pr.yml/badge.svg)](https://github.com/YOUR-USERNAME/Revanced-auto/actions/workflows/build-pr.yml)
[![License](https://img.shields.io/github/license/YOUR-USERNAME/Revanced-auto)](./LICENSE)

Automated APK patching and building system for ReVanced and RVX (ReVanced
Extended) applications.

## Features

- **Multi-App Building**: Build multiple apps in parallel or sequentially
- **Flexible Configuration**: TOML-based configuration with global and
  app-specific settings
- **Multiple Download Sources**: APKMirror, Uptodown, and Archive.org with
  automatic fallback
- **Version Control**: Support for specific versions, auto-detection, latest,
  and dev builds
- **Optimization Options**: AAPT2 resource optimization, library stripping
  (riplib), and zipalign
- **Signature Verification**: Automatic APK signature validation
- **Modular Architecture**: Clean separation of concerns with reusable library
  modules
- **Retry Logic**: Exponential backoff for network requests

## Quick Start

### Prerequisites

- **Required**: Bash 4.0+, Java 21+, jq, zip, curl or wget
- **Recommended**: optipng (for asset optimization)

### Installation

1. Clone this repository:

```bash
git clone <repository-url>
cd <repository-directory>
```

1. The project includes all necessary binaries in `bin/`:
   - `apksigner.jar` - APK signing tool
   - `dexlib2.jar` - DEX manipulation
   - `paccer.jar` - Patch integrity checker
   - `aapt2` - Android Asset Packaging Tool (arch-specific)
   - `htmlq` - HTML parser for APKMirror (arch-specific)
   - `toml` (tq) - TOML parser (arch-specific)

1. Ensure scripts are executable:

```bash
chmod +x build.sh utils.sh extras.sh scripts/*.sh
```

### Basic Usage

Build all enabled apps from `config.toml`:

```bash
./build.sh config.toml
```

Build a specific app:

```bash
# Edit config.toml and set enabled = true for your desired app
./build.sh config.toml
```

Clean build artifacts:

```bash
./build.sh clean
```

## Configuration

The `config.toml` file controls all build settings. You can create this file in two ways:

1. **Configuration Generator** (Recommended): [Web-based tool](https://YOUR-USERNAME.github.io/Revanced-auto/config-generator/) for creating configurations without manual editing
2. **Manual Editing**: See [CONFIG.md](CONFIG.md) for detailed documentation

### Global Settings

```toml
parallel-jobs = 1              # Number of parallel builds
compression-level = 9           # ZIP compression (0-9)
patches-version = "dev"         # dev, latest, or version tag
cli-version = "dev"             # dev, latest, or version tag
patches-source = "anddea/revanced-patches"
cli-source = "inotia00/revanced-cli"
rv-brand = "RVX"               # Brand name
arch = "arm64-v8a"             # Default architecture
riplib = true                  # Strip unnecessary libraries
enable-aapt2-optimize = true   # Resource optimization
```

### App Configuration

```toml
[YouTube-Extended]
enabled = true
app-name = "YouTube"
version = "auto"               # auto, latest, beta, or specific version
patches-source = "anddea/revanced-patches"
cli-source = "inotia00/revanced-cli"
rv-brand = "RVX"

excluded-patches = "'Enable debug logging'"
patcher-args = ["-e", "Custom branding icon for YouTube", "-OappIcon=mnt"]

# Download sources (at least one required)
uptodown-dlurl = "https://youtube.en.uptodown.com/android"
apkmirror-dlurl = "https://apkmirror.com/apk/google-inc/youtube"
archive-dlurl = "https://archive.org/download/jhc-apks/apks/com.google.android.youtube"
```

## Architecture

The project is organized into modular components:

```text
.
├── build.sh              # Main build orchestration script
├── utils.sh              # Utility loader (sources all lib modules)
├── config.toml           # Build configuration
├── bin/                 # Prebuilt binaries and tools
│   ├── apksigner.jar
│   ├── dexlib2.jar
│   ├── paccer.jar
│   ├── aapt2/           # Architecture-specific AAPT2
│   ├── htmlq/           # HTML parser
│   └── toml/            # TOML parser (tq)
├── lib/                 # Modular library components
│   ├── logger.sh         # Logging functions
│   ├── helpers.sh        # General utilities
│   ├── config.sh         # Configuration parsing
│   ├── network.sh        # HTTP requests with retry
│   ├── prebuilts.sh      # ReVanced CLI/patches management
│   ├── download.sh       # APK downloads
│   └── patching.sh      # APK patching and building
├── scripts/             # Optional optimization scripts
│   ├── aapt2-optimize.sh      # Resource optimization
│   ├── optimize-assets.sh      # PNG optimization
│   └── unused-strings.sh      # Remove unused resources
├── ks.keystore          # Default keystore for signing
└── sig.txt             # Known APK signatures
```

## Build Process

1. **Prerequisites Check**: Verify Java, jq, and other required tools
1. **Configuration Load**: Parse config.toml and set defaults
1. **Download Prebuilts**: Fetch ReVanced CLI and patches from GitHub
1. **Process Each App**:
   - Detect compatible version (if version = "auto")
   - Download stock APK from available sources
   - Verify APK signature
   - Apply ReVanced patches
   - Apply optimizations (zipalign, aapt2)
1. **Output**: Patched APKs in `build/` directory
1. **Generate**: build.md with build notes and changelogs

## Output

Build artifacts are placed in:

- `build/` - Final patched APKs
- `temp/` - Temporary files and cached downloads
- `build.md` - Build summary and changelogs

## Troubleshooting

### Enable Debug Logging

```bash
export LOG_LEVEL=0
./build.sh config.toml
```

### Common Issues

**Java version error**:

```text
Java version must be 21 or higher
```

Solution: Install OpenJDK Temurin 21 or later

**Download failures**:

```text
Request failed after 4 retries
```

Solution: Check internet connection, or try different download source

**Patch failures**:

```text
Building 'App-Name' failed
```

Solution: The app version may not be compatible with current patches. Try
setting `version = "auto"` or use a different version.

## Environment Variables

### Runtime Configuration

- `LOG_LEVEL` - Set to 0 for debug output (default: 1)
- `MAX_RETRIES` - Maximum retry attempts for network requests (default: 4)
- `INITIAL_RETRY_DELAY` - Initial retry delay in seconds (default: 2)
- `CONNECTION_TIMEOUT` - Connection timeout in seconds (default: 10)
- `GITHUB_TOKEN` - GitHub API token for authenticated requests (optional)
- `BUILD_MODE` - Set to "dev" or "stable" to force dev/stable patches

### Signing Configuration (Required)

- `KEYSTORE_PASSWORD` - Keystore password (required for building)
- `KEYSTORE_ENTRY_PASSWORD` - Key entry password (required for building)
- `KEYSTORE_PATH` - Path to keystore file (default: ks.keystore)
- `KEYSTORE_ALIAS` - Key alias (default: jhc)
- `KEYSTORE_SIGNER` - Signer name (default: jhc)

**Note**: For CI/CD workflows, set `KEYSTORE_PASSWORD` and
`KEYSTORE_ENTRY_PASSWORD` as repository secrets.

## Scripts

### build.sh

Main build script. Usage:

```bash
./build.sh [config.toml] [--config-update]
./build.sh clean
```

### extras.sh

Utility functions for CI/CD workflows:

```bash
./extras.sh separate-config <config.toml> <app_name> <output.toml>
./extras.sh combine-logs <logs_directory>
```

## Optimization

### AAPT2 Optimization

Enable in `config.toml`:

```toml
enable-aapt2-optimize = true
arch = "arm64-v8a"
```

Reduces APK size by keeping only:

- English language
- xxhdpi density
- arm64-v8a architecture

### Library Stripping (riplib)

Enable in `config.toml`:

```toml
riplib = true
```

Removes unnecessary native libraries:

- Strips x86 and x86_64 (ARM devices don't need them)
- Reduces APK size by 20-40%

## Security

### APK Signature Scheme Enforcement

All built APKs are signed with **APK Signature Scheme v1 and v2 only**. Higher
signature schemes (v3, v4) are explicitly disabled to ensure maximum
compatibility and predictable security characteristics. This is enforced via
post-patch re-signing using `apksigner.jar`.

### CI/CD Security

- Release artifacts are only published from the trusted repository (not from
  forks)
- Pull requests can build but cannot publish releases
- Keystore credentials must be configured as GitHub repository secrets

## Contributing

When contributing:

1. Maintain the modular library structure
1. Add appropriate logging at correct levels
1. Handle errors gracefully
1. Update documentation for new features
1. Test with various configurations
1. Maintain backward compatibility

## CI/CD

This repository includes automated workflows for building and releasing APKs:

- **Daily Builds**: Automated builds at 06:00 UTC daily
- **Manual Builds**: On-demand builds via GitHub Actions
- **PR Validation**: Automatic testing on pull requests

See [WORKFLOWS.md](.github/WORKFLOWS.md) for detailed workflow documentation.

## Tools & Resources

- **[Configuration Generator](https://YOUR-USERNAME.github.io/Revanced-auto/config-generator/)** - Create config.toml interactively
- **[Workflow Documentation](.github/WORKFLOWS.md)** - CI/CD setup and usage
- **[Security Policy](SECURITY.md)** - Security guidelines and reporting

## License

See [LICENSE](LICENSE) file for details.

## Acknowledgments

- [ReVanced](https://github.com/ReVanced) - Original ReVanced project
- [anddea/revanced-patches](https://github.com/anddea/revanced-patches) - Extended patches
- [inotia00/revanced-cli](https://github.com/inotia00/revanced-cli) - Extended CLI
- [j-hc](https://github.com/j-hc) - Original build system inspiration
