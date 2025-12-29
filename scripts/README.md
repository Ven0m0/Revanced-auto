# Optimization Scripts

This directory contains optimization scripts for reducing APK size and improving performance.

## Scripts

### aapt2-optimize.sh

Optimizes APK files using Android's aapt2 tool to keep only specific resources:
- **Language**: English (en) only
- **Density**: xxhdpi only
- **Architecture**: arm64-v8a only

**Usage:**
```bash
./aapt2-optimize.sh input.apk output.apk
```

**Configuration:**
Enable in `config.toml`:
```toml
enable-aapt2-optimize = true
arch = "arm64-v8a"
```

The optimization is automatically applied during the build process when enabled and building for arm64-v8a architecture.

### optimize-assets.sh

Optimizes PNG assets using optipng to reduce file sizes without quality loss.

**Source:** [brave-oled-dark/scripts/optimize-assets.sh](https://github.com/Ven0m0/brave-oled-dark/blob/main/scripts/optimize-assets.sh)

**Usage:**
```bash
cd <extracted-apk-directory>
/path/to/optimize-assets.sh
```

**Requirements:**
- `optipng` must be installed

### unused-strings.sh

Removes unused string resources from Android XML files to reduce APK size.

**Source:** [brave-oled-dark/scripts/unused-strings.sh](https://github.com/Ven0m0/brave-oled-dark/blob/main/scripts/unused-strings.sh)

**Usage:**
```bash
cd <decompiled-apk-directory>
/path/to/unused-strings.sh
```

**How it works:**
1. Scans all XML and smali files for string references
2. Compares with defined strings in strings.xml
3. Removes strings that are never referenced

## Additional Resources

### Enhancify

For advanced APK patching features, check out [Enhancify](https://github.com/Graywizard888/Enhancify), a custom Revancify fork with extra features including:
- Custom GitHub token support
- Network acceleration
- Multiple APK format support (APK, APKM, XAPK)
- Custom keystore management
- Shizuku/Rish installation support

## Notes

- All optimization scripts are optional and can be run manually
- The aapt2 optimization is integrated into the build pipeline when enabled
- optimize-assets.sh and unused-strings.sh are standalone utilities for manual optimization
