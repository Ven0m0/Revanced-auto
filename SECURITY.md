# Security Policy

## Supported Versions

We release security updates for the following versions:

| Version | Supported          |
| ------- | ------------------ |
| Latest (main branch) | :white_check_mark: |
| Older commits | :x: |

We recommend always using the latest version from the `main` branch.

## Security Measures

### Build System Security

This project implements multiple security measures:

1. **No eval() Usage**: All bash scripts avoid `eval` to prevent command injection
2. **Credential Protection**: Passwords passed via environment variables, not command-line arguments
3. **Input Validation**: All external inputs (URLs, versions, configs) are validated
4. **Path Traversal Protection**: File operations validate paths to prevent directory traversal
5. **APK Signature Verification**: Downloaded APKs verified against known good signatures
6. **Race Condition Prevention**: File locking (flock) for concurrent operations

### Recent Security Improvements (2026-01-12)

**Fixed Vulnerabilities**:
- Command injection via eval (CRITICAL) - Eliminated
- Password exposure via /proc (CRITICAL) - Fixed with environment variables
- Race conditions in downloads (HIGH) - Fixed with proper flock
- Path traversal in Archive.org downloads (MEDIUM) - Added validation

See `.claude/context-snapshots/2026-01-12-code-review-security-improvements.md` for details.

## Reporting a Vulnerability

### Where to Report

**Please DO NOT** create a public GitHub issue for security vulnerabilities.

Instead, report security issues via:
- **Email**: [YOUR-EMAIL@example.com]
- **GitHub Security Advisories**: [Use the "Security" tab → "Report a vulnerability"]

### What to Include

Please include:
1. **Description**: Clear description of the vulnerability
2. **Impact**: What an attacker could achieve
3. **Reproduction Steps**: How to reproduce the issue
4. **Affected Versions**: Which versions are affected
5. **Suggested Fix** (optional): How you think it could be fixed

### Response Timeline

- **Acknowledgment**: Within 48 hours
- **Initial Assessment**: Within 1 week
- **Fix Timeline**: Depends on severity
  - Critical: 1-3 days
  - High: 1 week
  - Medium: 2 weeks
  - Low: Next release

## Security Best Practices for Users

### Keystore Management

**DO**:
- Store keystore credentials in GitHub Secrets (for CI/CD)
- Use environment variables for passwords
- Keep keystore file secure and backed up
- Use strong passwords (16+ characters)

**DON'T**:
- Commit keystore passwords to git
- Share keystore files publicly
- Use weak or default passwords
- Pass passwords as command-line arguments

### Configuration Security

**DO**:
- Validate `config.toml` before use
- Use HTTPS URLs only for downloads
- Verify patch sources are from trusted repos
- Review excluded/included patches

**DON'T**:
- Download APKs from untrusted sources
- Use patches from unknown repositories
- Disable signature verification
- Run with elevated privileges unnecessarily

### CI/CD Security

**DO**:
- Set repository secrets for keystore credentials
- Enable fork-safe publishing checks
- Review workflow permissions regularly
- Keep workflows in `.github/workflows/` directory

**DON'T**:
- Push secrets to repository
- Allow forks to publish releases
- Grant excessive workflow permissions
- Run untrusted code in workflows

## Known Security Considerations

### APK Signature Scheme

Built APKs are signed with **v1 and v2 only** (v3/v4 disabled). This is intentional for maximum compatibility but means:
- APKs can be re-signed by users
- No APK signature lineage protection
- Compatible with older Android versions (4.4+)

If you need v3/v4 signatures, modify `lib/patching.sh:patch_apk()`.

### Download Sources

APKs are downloaded from:
1. **APKMirror** - Generally trusted
2. **Uptodown** - Third-party, verify signatures
3. **Archive.org** - Historical, verify signatures

All downloads are verified against `sig.txt` known good signatures.

### Build Artifacts

Built APKs should be scanned with:
- VirusTotal or similar malware scanners
- APK analyzers (jadx, apktool)
- Runtime behavior monitoring

We do not guarantee the security of third-party patches.

## Secure Coding Guidelines

For contributors:

### Bash Security

1. **Always quote variables**: `"${var}"` not `$var`
2. **Use [[ ]] for tests**: Not `[ ]`
3. **Avoid eval**: Use arrays, name refs, or files instead
4. **Validate inputs**: Check format, range, and content
5. **Use set -euo pipefail**: Fail fast on errors

### Credential Handling

1. **Environment variables**: For passwords
2. **No command-line args**: Visible in /proc
3. **No logging**: Don't log secrets
4. **Cleanup**: Unset or clear after use

### File Operations

1. **Use mktemp**: For temporary files
2. **Validate paths**: Check for ".." and absolute paths
3. **flock for concurrency**: Prevent race conditions
4. **Check permissions**: Before reading/writing

### Network Operations

1. **HTTPS only**: No HTTP downloads
2. **Verify SSL**: Don't disable certificate checks
3. **Timeout limits**: Prevent hanging
4. **Retry with backoff**: Exponential delays

## Security Tools

### Pre-commit Hook

The repository includes a pre-commit hook that checks for:
- eval usage
- Unquoted variables
- Hardcoded secrets
- Bash syntax errors

Enable: Pre-commit hook already installed at `.git/hooks/pre-commit`

### Shellcheck

Run shellcheck on all bash scripts:
```bash
shellcheck lib/*.sh build.sh extras.sh utils.sh
```

Or use the workflow: `.github/workflows/shellcheck.yml` (if added)

### Testing

Run security tests:
```bash
# Syntax validation
for f in lib/*.sh; do bash -n "$f"; done

# Automated tests
./test-multi-source.sh

# Check for secrets in git history
git log -p | grep -i "password\|secret\|token" | grep -v "^-"
```

## Dependency Security

### Binary Tools

The repository includes prebuilt binaries in `bin/`:
- `apksigner.jar` - From Android SDK Build Tools
- `dexlib2.jar` - From ReVanced project
- `paccer.jar` - Custom patch checker
- `aapt2` - From Android SDK Build Tools
- `htmlq` - From htmlq project
- `tq` - TOML parser

**Verification**:
- All binaries are from official sources
- SHA256 checksums documented (TBD: add checksums)
- Update process tracked in git history

### Patch Sources

Default patch sources:
- `anddea/revanced-patches` - Community trusted
- `inotia00/revanced-cli` - Extended CLI fork

**Note**: You can use any GitHub repo as patch source, but we only vouch for default sources.

## Incident Response

If a security incident is discovered:

1. **Immediate Actions**:
   - Assess impact and scope
   - Identify affected versions
   - Develop and test fix

2. **Communication**:
   - Notify reporter privately
   - Create security advisory
   - Coordinate public disclosure

3. **Fix Deployment**:
   - Release patched version
   - Update documentation
   - Publish security advisory

4. **Post-Incident**:
   - Root cause analysis
   - Update security measures
   - Improve testing/validation

## Security Audit History

| Date | Type | Findings | Status |
|------|------|----------|--------|
| 2026-01-12 | Comprehensive Code Review | 5 vulnerabilities fixed | ✅ Resolved |

See context snapshots in `.claude/context-snapshots/` for detailed audit reports.

## Additional Resources

- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [Bash Security Best Practices](https://mywiki.wooledge.org/BashGuide/Practices)
- [GitHub Security Best Practices](https://docs.github.com/en/code-security)

## Questions?

For non-security questions:
- GitHub Issues: [Your repository]/issues
- Documentation: README.md, CLAUDE.md, CONFIG.md

For security concerns: See "Reporting a Vulnerability" above.

---

**Last Updated**: 2026-01-12
**Version**: 1.0.0
