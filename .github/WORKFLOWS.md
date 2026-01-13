# GitHub Actions Workflows

This document explains the GitHub Actions workflows in this repository.

## Overview

The repository uses multiple workflows for different purposes:

1. **Daily Builds** - Automated daily builds at 06:00 UTC
2. **Manual Builds** - On-demand builds via workflow_dispatch
3. **PR Validation** - Automated testing for pull requests
4. **Legacy CI** - Existing workflow at 16:00 UTC (optional)

## Workflows

### 1. Daily Build (`build-daily.yml`)

**Purpose**: Automated daily builds matching RookieEnough schedule

**Triggers**:
- Schedule: Daily at 06:00 UTC (`0 6 * * *`)
- Manual: workflow_dispatch with build_mode selection

**Features**:
- Update check (only builds if patches/apps updated)
- Calls reusable `build.yml` workflow
- Matrix strategy for parallel app builds
- Automated release management
- Old workflow cleanup

**Environment Variables Required**:
- `KEYSTORE_PASSWORD` (secret)
- `KEYSTORE_ENTRY_PASSWORD` (secret)
- `GITHUB_TOKEN` (auto-provided)

**Usage**:
```yaml
# Runs automatically at 06:00 UTC daily
# Or trigger manually from Actions tab
```

### 2. Manual Build (`build-manual.yml`)

**Purpose**: Build specific apps on-demand with custom parameters

**Triggers**:
- Manual: workflow_dispatch only

**Inputs**:
- `app_name` (required) - App to build (e.g., YouTube-Extended)
- `version` (optional) - Version override (default: auto)
- `architecture` (optional) - arm64-v8a, armeabi-v7a, or both (default: arm64-v8a)
- `build_mode` (optional) - stable or dev (default: stable)
- `publish_release` (optional) - Publish to GitHub Releases (default: true)

**Features**:
- Single app builds for testing
- Version and architecture override
- Optional release publishing
- Extended artifact retention (7 days)

**Usage**:
```bash
# From GitHub UI: Actions → Manual Build → Run workflow
# Select app, version, architecture, and publish options
```

### 3. PR Validation (`build-pr.yml`)

**Purpose**: Validate pull requests before merging

**Triggers**:
- Pull requests to main/master
- Only when relevant files change (*.sh, *.toml, lib/, scripts/, workflows/)

**Checks**:
1. Prerequisites (Java 21+, jq, zip, curl)
2. Bash syntax validation (all scripts)
3. Automated test suite
4. Test build (single app)
5. Results posted as PR comment

**Features**:
- No secrets required (skips signing)
- Fast feedback on PRs
- Detailed step summary
- Automated PR comments
- Fork-safe (no publishing)

**Permissions**:
- `contents: read` - Checkout code
- `pull-requests: write` - Post comments
- `actions: read` - Access workflow data

### 4. Legacy CI (`ci.yml`)

**Purpose**: Existing daily build workflow at 16:00 UTC

**Status**: ⚠️ **Optional** - Can coexist with build-daily.yml or be disabled

**Triggers**:
- Schedule: Daily at 16:00 UTC (`0 16 * * *`)
- Manual: workflow_dispatch

**Note**: This is the original CI workflow. You can:
- **Keep both**: Two daily builds (06:00 and 16:00 UTC)
- **Disable**: Rename to `ci.yml.disabled` if only want 06:00 UTC builds
- **Update**: Change schedule to match build-daily.yml (not recommended)

### 5. Build (Reusable) (`build.yml`)

**Purpose**: Reusable workflow for actual APK building

**Triggers**:
- Called by other workflows (workflow_call)
- Manual: workflow_dispatch

**Features**:
- Matrix strategy from config.toml
- Parallel app builds
- Per-app artifacts
- Combined build logs
- Release management
- Fork-safe publishing

**Inputs**:
- `from_ci` (boolean) - Running from CI (default: true)
- `build_mode` (string) - stable or dev (default: stable)

## Workflow Relationships

```bash
Daily Build (06:00 UTC)
    ↓
    Check for updates
    ↓
    Build (reusable) ──→ Matrix builds ──→ Release

Manual Build
    ↓
    Build single app ──→ Optional release

PR Validation
    ↓
    Syntax + Tests + Test build (no release)

Legacy CI (16:00 UTC) [optional]
    ↓
    Check for updates
    ↓
    Build (reusable) ──→ Matrix builds ──→ Release
```

## Security

### Fork Safety

All workflows that publish releases include this check:
```yaml
if: github.repository == github.event.repository.full_name
```

This prevents forks from publishing to your releases.

### Secrets Required

**Required for building**:
- `KEYSTORE_PASSWORD` - APK signing keystore password
- `KEYSTORE_ENTRY_PASSWORD` - APK signing key entry password

**Auto-provided**:
- `GITHUB_TOKEN` - Automatic, no configuration needed

### Setting Secrets

1. Go to repository Settings
2. Secrets and variables → Actions
3. New repository secret
4. Add both keystore secrets

## Release Management

### Release Strategy

**Tag**: `latest` (single rolling release)

**Process**:
1. Delete old "latest" release and tag
2. Create new "latest" release
3. Upload all APK artifacts
4. Generate release notes from build logs

**Script**: `scripts/release-manager.sh`

### Release Notes Format

```markdown
# ReVanced Builds - YYYY-MM-DD

## 📦 Included Apps
[Auto-generated from build.md files]

## 📥 Installation
[Instructions for users]

## ⚙️ Build Information
- Build Date
- Patches sources
- Technical details
```

## Customization

### Changing Build Schedule

Edit the cron expression in workflow files:

```yaml
schedule:
  - cron: "0 6 * * *"  # 06:00 UTC daily
```

Cron format: `minute hour day month weekday`

Common schedules:
- `0 6 * * *` - 06:00 UTC daily
- `0 */6 * * *` - Every 6 hours
- `0 0 * * 0` - Weekly on Sunday
- `0 6 * * 1-5` - Weekdays only

### Disabling Workflows

To disable a workflow:
1. Rename file: `workflow.yml` → `workflow.yml.disabled`
2. Or delete the file
3. Commit changes

### Adding New Apps to Matrix

Apps are automatically included from `config.toml`:
- All `[AppName]` sections with `enabled = true`
- Apps with `arch = "both"` create 2 matrix entries

No workflow changes needed!

## Monitoring

### Build Status

Check workflow status:
- GitHub repository → Actions tab
- Look for ✓ (success) or ✗ (failure)
- Click run for detailed logs

### Release Status

Check releases:
- GitHub repository → Releases
- "latest" tag should have recent APKs
- Release notes show build details

### Notifications

Configure in repository settings:
- Settings → Notifications
- Email notifications for workflow failures
- GitHub mobile app notifications

## Troubleshooting

### Build Failures

**"No updates needed"**
- Normal - no patches or apps updated
- Build skipped (saves resources)

**"Keystore password not set"**
- Add secrets to repository settings
- Check secret names match exactly

**"Failed to create release"**
- Check `GITHUB_TOKEN` permissions
- Ensure fork-safe check isn't blocking
- Verify `gh` CLI authentication in runner

**"Matrix is empty"**
- No enabled apps in config.toml
- Check app `enabled = true` settings

### PR Validation Issues

**"Syntax validation failed"**
- Fix bash syntax errors
- Run locally: `bash -n script.sh`

**"Tests failed"**
- Fix failing tests
- Run locally: `./test-multi-source.sh`

**"Build failed before signing"**
- Real issue - needs investigation
- Check logs for specific error

### Workflow Not Triggering

**Schedule not running**:
- GitHub disables schedules after 60 days of repo inactivity
- Make a commit to re-enable
- Or trigger manually

**PR validation not running**:
- Check file paths match trigger patterns
- PR must target main/master branch

## Performance

### Build Times

Typical build times:
- Single app: 3-5 minutes
- Matrix (3 apps): 5-8 minutes (parallel)
- Full build (all apps): 10-20 minutes

### Cost Optimization

GitHub Actions free tier:
- 2,000 minutes/month for private repos
- Unlimited for public repos

Optimizations:
- Matrix parallelization (faster, same cost)
- Update checks (skip unnecessary builds)
- Artifact retention (1 day for CI, 7 for manual)

## Advanced Usage

### Custom Matrix

Edit `scripts/generate_matrix.sh` to customize matrix generation:
```bash
# Example: Add custom fields
jq -c '{include: [to_entries[] | ... | {id: .key, custom: "value"}]}'
```

### Multiple Daily Builds

Keep both `ci.yml` (16:00 UTC) and `build-daily.yml` (06:00 UTC):
- Good for active projects
- Two chances to catch updates
- Users in different timezones get fresh builds

Or consolidate to single schedule:
- Disable one workflow
- Save Actions minutes

### Release Variants

Create multiple release tags:
```yaml
# build-daily.yml (stable builds)
tag: "latest"

# build-dev.yml (dev builds)
tag: "latest-dev"
```

## Migration from RookieEnough

If migrating from RookieEnough/Revanced-AutoBuilds:

**Similarities**:
- Daily 06:00 UTC schedule ✓
- Matrix builds ✓
- Single "latest" release ✓
- Fork-safe publishing ✓

**Differences**:
- Uses existing bash build system (not Python)
- Leverages `build.sh` and `config.toml`
- More manual control options
- Separate PR validation workflow

**Migration Steps**:
1. Copy your `config.toml` settings
2. Set repository secrets
3. Enable workflows
4. First run will create "latest" release

## Support

For issues with workflows:
1. Check Actions tab for detailed logs
2. Review this documentation
3. Check `.claude/docs/plans/revanced-autobuilds-integration-design.md`
4. Create GitHub issue with workflow run link

---

**Last Updated**: 2026-01-12
**Version**: 1.0.0
