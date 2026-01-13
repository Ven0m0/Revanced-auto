# Advanced Features Documentation

This document describes the advanced automation features available in ReVanced Builder.

## Table of Contents

1. [Changelog Automation](#changelog-automation)
2. [Build Cache System](#build-cache-system)
3. [Dependency Update Checker](#dependency-update-checker)

---

## Changelog Automation

Automatically generate comprehensive changelogs from git commits and ReVanced patches updates.

### Features

- **Commit Parsing**: Analyzes git commits with conventional commit format support
- **Categorization**: Automatically categorizes changes (features, fixes, improvements, etc.)
- **Patches Changelog**: Fetches and includes ReVanced patches changelog from GitHub releases
- **Multiple Formats**: Supports Markdown, JSON, and plain text output
- **Integration**: Seamlessly integrates with release-manager.sh

### Usage

#### Standalone

```bash
# Generate markdown changelog for recent changes
scripts/changelog-generator.sh

# Generate changelog between two tags
scripts/changelog-generator.sh --from v1.0.0 --to v2.0.0

# Generate JSON changelog
scripts/changelog-generator.sh --format json

# Save to file
scripts/changelog-generator.sh --output CHANGELOG.md

# Without patches changelog (faster)
scripts/changelog-generator.sh --no-patches
```

#### With Release Manager

The changelog generator is automatically used by `release-manager.sh`:

```bash
# Full release workflow with enhanced changelog
scripts/release-manager.sh manage latest build build-logs
```

### Commit Format

For best results, use conventional commit format:

```
<type>(<scope>): <description>

[optional body]
```

**Supported types:**
- `feat` / `feature`: New features
- `fix` / `bugfix`: Bug fixes
- `perf` / `performance`: Performance improvements
- `refactor` / `style`: Code refactoring
- `docs` / `doc`: Documentation changes
- `test` / `tests`: Test updates
- `build` / `ci` / `chore`: Build system / CI changes
- `security` / `sec`: Security fixes

**Example:**
```bash
git commit -m "feat(patching): add multi-source patch support"
git commit -m "fix(download): correct APKMirror fallback logic"
git commit -m "perf(cache): optimize cache lookup performance"
```

### Environment Variables

- `GITHUB_TOKEN`: GitHub personal access token (for higher API rate limits)
- `GITHUB_API_URL`: Custom GitHub API URL (default: https://api.github.com)

### Output Example

```markdown
# Changelog - 2026-01-12

## 🚀 What's New

### ✨ New Features

- **patching**: add multi-source patch support ([a94c86a])
- **ci**: automated daily builds with GitHub Actions ([3618b6c])

### 🐛 Bug Fixes

- **download**: correct APKMirror fallback logic ([5ac4ce5])

### ⚡ Performance

- **cache**: optimize cache lookup performance ([bef21a0])

## 📦 ReVanced Patches Updates

### anddea/revanced-patches

**Current Version**: `v4.16.0`

...
```

---

## Build Cache System

Intelligent caching system with validation and automatic cleanup for improved build performance.

### Features

- **Smart Caching**: TTL-based caching with automatic expiration
- **Integrity Validation**: SHA-256 checksum verification
- **Metadata Tracking**: JSON-based cache index with detailed metadata
- **Automatic Cleanup**: Remove expired and orphaned cache entries
- **Pattern Matching**: Clean specific cache entries by pattern

### Architecture

The cache system uses a JSON index file (`.cache-index.json`) to track:
- Creation and access timestamps
- File size and checksum
- Source URL
- Custom TTL per entry

### Usage

#### Initialize Cache

```bash
./build.sh cache init
```

#### View Cache Statistics

```bash
./build.sh cache stats
```

**Example output:**
```
Cache Statistics:
  Total entries: 15
  Total size: 245.3 MiB
  Expired entries: 3
  Cache directory: temp
```

#### Clean Expired Entries

```bash
# Remove only expired entries
./build.sh cache cleanup

# Remove expired entries + orphaned index entries
./build.sh cache cleanup force
```

#### Clean by Pattern

```bash
# Remove all APK files from cache
./build.sh cache clean '.*\.apk'

# Remove cache for specific app
./build.sh cache clean 'youtube.*'

# Remove all cache entries
./build.sh cache clean
```

### Programmatic API

The cache system is available as a library module (`scripts/lib/cache.sh`):

```bash
# In your scripts
source utils.sh

# Check if cached file is valid
if cache_is_valid "/path/to/file.apk" 86400; then
    echo "Using cached file"
else
    # Download file
    cache_download "https://example.com/file.apk" "/path/to/file.apk" 86400
fi

# Add file to cache
cache_put "/path/to/file.apk" "https://example.com/file.apk" 86400

# Remove from cache
cache_remove "/path/to/file.apk"

# Get cache path for key
cache_path=$(get_cache_path "youtube-19.16.39" "apks")
```

### Configuration

Default cache settings (can be overridden via environment variables):

- `CACHE_DIR`: Cache directory (default: `temp`)
- `DEFAULT_CACHE_TTL`: Default TTL in seconds (default: 86400 = 24 hours)

### Cache Structure

```
temp/
├── .cache-index.json          # Cache metadata
├── anddea-rv/
│   └── patches-v4.16.0.rvp
├── inotia00-rv/
│   └── revanced-cli-dev.jar
└── youtube/
    └── youtube-19.16.39-arm64-v8a.apk
```

### Benefits

- **Faster Builds**: Reuse previously downloaded files
- **Reduced Bandwidth**: Skip re-downloading unchanged files
- **Integrity Assurance**: Verify file integrity automatically
- **Storage Management**: Automatic cleanup of old files

---

## Dependency Update Checker

Automated monitoring of ReVanced CLI, patches, and APK versions for updates.

### Features

- **CLI Updates**: Monitor ReVanced CLI versions
- **Patches Updates**: Track patches from multiple sources
- **Multiple Formats**: Output as text, JSON, or Markdown
- **GitHub Integration**: Automatic issue creation for updates
- **Selective Checking**: Check specific components only

### Usage

#### Manual Checks

```bash
# Check all dependencies
scripts/dependency-checker.sh

# Check only CLI
CHECK_MODE=cli scripts/dependency-checker.sh

# Check only patches
CHECK_MODE=patches scripts/dependency-checker.sh

# Generate JSON report
OUTPUT_FORMAT=json scripts/dependency-checker.sh

# Generate Markdown report
OUTPUT_FORMAT=markdown scripts/dependency-checker.sh > dependency-report.md

# With custom config file
scripts/dependency-checker.sh config-custom.toml
```

#### Automated Checks (GitHub Actions)

The repository includes a GitHub Actions workflow (`.github/workflows/dependency-check.yml`) that:

1. Runs daily at 00:00 UTC
2. Checks for CLI and patches updates
3. Creates/updates GitHub issues when updates are found
4. Comments on relevant PRs
5. Uploads report as artifact

**Manual trigger:**

1. Go to Actions → Dependency Update Check
2. Click "Run workflow"
3. Select check mode (all, cli, patches, apks)
4. Choose whether to create issue
5. Run workflow

### Output Formats

#### Text (Default)

```
Dependency Update Report
========================

Generated: 2026-01-12 15:30:00

[cli] inotia00/revanced-cli
  Current: latest
  Latest:  v4.6.0
  Status:  Up to date

[patches] anddea/revanced-patches
  Current: v4.15.0
  Latest:  v4.16.0
  Status:  UPDATE AVAILABLE

⚠ Updates are available!
```

#### JSON

```json
[
  {
    "component": "cli",
    "source": "inotia00/revanced-cli",
    "current_version": "latest",
    "latest_version": "v4.6.0",
    "update_available": false
  },
  {
    "component": "patches",
    "source": "anddea/revanced-patches",
    "current_version": "v4.15.0",
    "latest_version": "v4.16.0",
    "update_available": true
  }
]
```

#### Markdown

```markdown
# Dependency Update Report

**Generated**: 2026-01-12 15:30:00

## Summary

### cli: inotia00/revanced-cli

- **Current Version**: `latest`
- **Latest Version**: `v4.6.0`
- **Status**: ✅ Up to date

### patches: anddea/revanced-patches

- **Current Version**: `v4.15.0`
- **Latest Version**: `v4.16.0`
- **Status**: 🔄 **Update Available**

## 🔔 Action Required

Updates are available. Consider updating your configuration.
```

### Environment Variables

- `CHECK_MODE`: What to check (`all`, `cli`, `patches`, `apks`)
- `OUTPUT_FORMAT`: Output format (`text`, `json`, `markdown`)
- `GITHUB_TOKEN`: GitHub token for higher API rate limits
- `GITHUB_API_URL`: Custom GitHub API URL

### GitHub Actions Configuration

The workflow supports:

- **Scheduled runs**: Daily at 00:00 UTC
- **Manual dispatch**: Trigger manually with options
- **Automatic issue management**: Creates/updates issues
- **PR comments**: Comments on relevant pull requests
- **Artifact upload**: Saves reports for 30 days

**Permissions required:**
- `contents: read` - Read repository content
- `issues: write` - Create and update issues

### Integration with CI/CD

Add to your workflow:

```yaml
- name: Check dependencies
  run: |
    OUTPUT_FORMAT=markdown scripts/dependency-checker.sh > report.md
    cat report.md >> $GITHUB_STEP_SUMMARY
```

### Updating Dependencies

When updates are found:

1. Review the dependency report
2. Check changelog for breaking changes
3. Update `config.toml`:
   ```toml
   cli-version = "v4.6.0"
   patches-version = "v4.16.0"
   ```
4. Test the build locally
5. Commit and push changes

### Future Enhancements

- APK version checking from APKMirror/Uptodown
- Automated PR creation for updates
- Compatibility matrix verification
- Security vulnerability scanning

---

## Tips and Best Practices

### Changelog Automation

1. **Use Conventional Commits**: Helps with automatic categorization
2. **Set GITHUB_TOKEN**: Avoid API rate limits
3. **Include Patches Changelog**: Provides context for users
4. **Customize Format**: Choose format based on your needs

### Build Cache System

1. **Regular Cleanup**: Run `./build.sh cache cleanup` weekly
2. **Monitor Size**: Check `./build.sh cache stats` regularly
3. **Adjust TTL**: Set appropriate TTL for your build frequency
4. **Pattern Cleaning**: Use patterns to clean specific categories

### Dependency Checker

1. **Enable Workflow**: Uncomment scheduled runs in workflow
2. **Review Reports**: Check reports before updating
3. **Test Updates**: Always test in a separate branch first
4. **Monitor Issues**: Keep an eye on auto-created issues

---

## Troubleshooting

### Changelog Generation Issues

**Problem**: "No releases found for repo"
- **Solution**: Repository may not have releases, or GITHUB_TOKEN is invalid

**Problem**: Empty changelog generated
- **Solution**: Check if commits exist in specified range

### Cache Issues

**Problem**: Cache index corrupted
- **Solution**: Delete `.cache-index.json` and run `./build.sh cache init`

**Problem**: High cache disk usage
- **Solution**: Run `./build.sh cache cleanup force`

### Dependency Checker Issues

**Problem**: "API rate limit exceeded"
- **Solution**: Set `GITHUB_TOKEN` environment variable

**Problem**: "Could not determine latest version"
- **Solution**: Check repository name format and network connectivity

---

## Contributing

Contributions to improve these features are welcome! Please see [CONTRIBUTING.md](../CONTRIBUTING.md) for guidelines.

## License

These features are part of ReVanced Builder and are released under the same license. See [LICENSE](../LICENSE) for details.
