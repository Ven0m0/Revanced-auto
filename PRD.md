# PRD: ReVanced Builder Refactor - Phases 3-5

## Introduction

Complete the codebase refactoring by improving dependency detection, replacing architecture-specific binaries with Python implementations, consolidating the modular library structure into a unified scripts directory, and ensuring all documentation accurately reflects the new architecture. This refactor eliminates brittle binary dependencies, simplifies maintenance, and improves cross-platform compatibility.

## Goals

- Implement intelligent aapt2 detection that auto-selects the best available option
- Clean repository of all temporary files, unused scripts, and deprecated documentation
- Replace htmlq binaries with Python-based HTML parsing using lxml
- Consolidate lib/ utilities into scripts/ directory with clear organization
- Update all documentation with architecture changes and inline code comments
- Maintain 100% functionality - no regressions in build pipeline

## User Stories

### Phase 3: Code Cleanup & Dependency Fixes

### US-001: Improve aapt2 detection with auto-detection
**Description:** As a developer, I want aapt2 detection to automatically choose the best available option so builds work across different environments without manual configuration.

**Acceptance Criteria:**
- [ ] Update `set_prebuilts()` in lib/helpers.sh to check for system aapt2 first using `command -v aapt2`
- [ ] If system aapt2 found, verify it's executable and set AAPT2 to system path
- [ ] If no system aapt2, fall back to bundled binary with architecture detection
- [ ] For x86_64 without bundled binary, log clear warning and attempt system binary or fail gracefully
- [ ] Add debug logging for which aapt2 is selected (system vs bundled, path)
- [ ] ShellCheck passes for modified file

### US-002: Remove temporary and build artifacts
**Description:** As a developer, I want the repository cleaned of build artifacts so the working directory is uncluttered.

**Acceptance Criteria:**
- [ ] Identify all files in temp/ directory (if any) and verify they're in .gitignore
- [ ] Identify all files in build/ directory (if any) and verify they're in .gitignore
- [ ] Remove any cached or temporary files not covered by .gitignore
- [ ] Verify temp/ and build/ directories are properly ignored in .gitignore
- [ ] No temporary files committed to git history (check with `git status`)

### US-003: Remove unused scripts and configurations
**Description:** As a developer, I want unused or deprecated scripts removed so the codebase is easier to navigate.

**Acceptance Criteria:**
- [ ] Audit all scripts in root and scripts/ directory
- [ ] Identify scripts not referenced by build.sh, utils.sh, or CI workflows
- [ ] Remove identified unused scripts (or document why they're kept)
- [ ] Check for orphaned test configs or example files
- [ ] Remove any configs not actively used or documented
- [ ] Update .gitignore if needed to exclude removed patterns

### US-004: Clean up deprecated documentation
**Description:** As a developer, I want outdated documentation removed so readers aren't confused by obsolete information.

**Acceptance Criteria:**
- [ ] Audit docs/ directory for deprecated or outdated files
- [ ] Remove documentation for removed features or old architectures
- [ ] Check for duplicate documentation (README vs docs/README, etc.)
- [ ] Remove or archive deprecated planning documents (if not needed for history)
- [ ] Verify all links in remaining docs still point to valid locations
- [ ] ShellCheck passes if any script references are updated

### Phase 4: Python Migration & Script Consolidation

### US-005: Create Python HTML parser using lxml
**Description:** As a developer, I need a Python-based HTML parser to replace htmlq binaries so we eliminate architecture-specific dependencies.

**Acceptance Criteria:**
- [ ] Create `scripts/html_parser.py` with lxml-based parsing
- [ ] Implement `scrape_text(html, selector)` function equivalent to htmlq --text
- [ ] Implement `scrape_attr(html, selector, attribute)` function equivalent to htmlq --attribute
- [ ] Accept HTML via stdin and selector/attribute via command-line arguments
- [ ] Output matches in same format as htmlq (one per line)
- [ ] Add proper error handling for invalid selectors or malformed HTML
- [ ] Include shebang `#!/usr/bin/env python3` and make executable
- [ ] Add docstring with usage examples

### US-006: Update download.sh to use Python HTML parser
**Description:** As a developer, I want lib/download.sh to use the new Python parser so htmlq binaries are no longer needed.

**Acceptance Criteria:**
- [ ] Replace `scrape_text()` calls in lib/helpers.sh to invoke `scripts/html_parser.py`
- [ ] Replace `scrape_attr()` calls in lib/helpers.sh to invoke `scripts/html_parser.py`
- [ ] Update function signatures to pipe HTML to Python script
- [ ] Verify APKMirror download flow works with new parser
- [ ] Verify Uptodown download flow works with new parser
- [ ] Test with sample HTML to ensure output matches previous htmlq behavior
- [ ] ShellCheck passes for modified files

### US-007: Move lib utilities to scripts directory
**Description:** As a developer, I want lib/*.sh files consolidated into scripts/ so the codebase has a single utilities location.

**Acceptance Criteria:**
- [ ] Move lib/logger.sh to scripts/lib/logger.sh
- [ ] Move lib/helpers.sh to scripts/lib/helpers.sh
- [ ] Move lib/config.sh to scripts/lib/config.sh
- [ ] Move lib/network.sh to scripts/lib/network.sh
- [ ] Move lib/cache.sh to scripts/lib/cache.sh
- [ ] Move lib/prebuilts.sh to scripts/lib/prebuilts.sh
- [ ] Move lib/download.sh to scripts/lib/download.sh
- [ ] Move lib/patching.sh to scripts/lib/patching.sh
- [ ] Move lib/checks.sh to scripts/lib/checks.sh
- [ ] Remove empty lib/ directory
- [ ] Update .gitignore if lib/ was specifically mentioned

### US-008: Update all shell script imports
**Description:** As a developer, I want all shell scripts updated to source from new scripts/lib/ location so the build pipeline continues to work.

**Acceptance Criteria:**
- [ ] Update utils.sh to source from scripts/lib/ instead of lib/
- [ ] Update LIB_DIR variable to point to scripts/lib/
- [ ] Test that `source utils.sh` still loads all modules successfully
- [ ] Update any direct sourcing in build.sh, check-env.sh, extras.sh
- [ ] Update references in CI workflow files (.github/workflows/)
- [ ] ShellCheck passes for all modified shell scripts

### US-009: Test build pipeline with new structure
**Description:** As a developer, I need to verify the complete build pipeline works with the new structure so we catch any regressions.

**Acceptance Criteria:**
- [ ] Run `./check-env.sh` and verify it completes successfully
- [ ] Run `./build.sh config.toml` in dry-run or with test config
- [ ] Verify all lib modules load correctly from scripts/lib/
- [ ] Verify Python HTML parser is invoked correctly
- [ ] Verify aapt2 detection selects appropriate binary
- [ ] Check logs for any errors or warnings about missing files
- [ ] Confirm build artifacts are created in expected locations

### Phase 5: Documentation Enhancement

### US-010: Update CLAUDE.md with architecture changes
**Description:** As a developer, I want CLAUDE.md updated to reflect the new scripts/lib/ structure and Python utilities so AI assistants have accurate context.

**Acceptance Criteria:**
- [ ] Update "Architecture" section to reference scripts/lib/ instead of lib/
- [ ] Update "Modular Library Structure" diagram/text to show scripts/lib/
- [ ] Document Python HTML parser in "Binary Tools" section
- [ ] Remove htmlq from "Binary Tools" section
- [ ] Update any code examples that reference lib/ paths
- [ ] Add note about lxml dependency for HTML parsing
- [ ] Update "Key Functions Reference" if any paths changed

### US-011: Update CONFIG.md and README.md
**Description:** As a developer, I want CONFIG.md and README.md updated so users see current prerequisites and paths.

**Acceptance Criteria:**
- [ ] Update README.md Prerequisites section to include Python 3.x and lxml
- [ ] Remove htmlq from Prerequisites in README.md
- [ ] Update README.md Installation section if bin/htmlq/ is mentioned
- [ ] Update CONFIG.md if any config paths changed (lib/ -> scripts/lib/)
- [ ] Update any troubleshooting sections that reference old paths
- [ ] Verify all command examples still work with new structure
- [ ] Check for references to lib/ directory and update to scripts/lib/

### US-012: Add inline documentation to Python utilities
**Description:** As a developer, I want Python scripts to have clear docstrings and comments so they're maintainable.

**Acceptance Criteria:**
- [ ] Add module-level docstring to scripts/html_parser.py
- [ ] Add docstrings to all functions in scripts/html_parser.py
- [ ] Include parameter types and return types in docstrings
- [ ] Add usage examples in module docstring
- [ ] Add inline comments for non-obvious logic (CSS selector handling, etc.)
- [ ] Follow PEP 257 docstring conventions
- [ ] Add error handling documentation

### US-013: Update developer documentation
**Description:** As a developer, I want developer docs updated so contributors understand the new architecture.

**Acceptance Criteria:**
- [ ] Update conductor/tech-stack.md if it references lib/ structure
- [ ] Update any architectural diagrams in docs/
- [ ] Add section on Python utilities to developer documentation
- [ ] Document when to add code to scripts/lib/ vs scripts/
- [ ] Update contribution guidelines if paths changed
- [ ] Verify all documentation cross-references are still valid
- [ ] Add Python lxml to dependency documentation

## Non-Goals

- No performance optimization beyond what new structure naturally provides
- No changes to core patching logic or ReVanced CLI integration
- No new features - purely refactoring existing functionality
- No migration of existing builds or cached data
- No changes to config.toml format or structure
- No removal of working functionality or supported use cases
- No updates to CI/CD workflows beyond path references

## Technical Considerations

### Dependencies
- **Python 3.x**: Already required for scripts/toml_get.py
- **lxml**: New dependency for HTML parsing (install: `pip install lxml`)
- **ShellCheck**: For validating shell script changes during development

### Architecture
- Current: `lib/*.sh` sourced by `utils.sh`
- Target: `scripts/lib/*.sh` sourced by `utils.sh`
- All functionality preserved, only paths change

### Risk Mitigation
- Test each phase independently before moving to next
- Keep git history clean with focused commits per user story
- Verify build pipeline after each significant change
- Use test configs to avoid breaking production builds

### Rollback Plan
If issues arise, rollback is straightforward:
1. Revert to last working commit
2. Address issues in isolated branch
3. Re-apply changes incrementally

## Success Criteria

All acceptance criteria for all user stories must be met:
- [ ] aapt2 detection works on all supported platforms
- [ ] Repository is clean of unused files and deprecated docs
- [ ] htmlq binaries removed, Python parser works for all download sources
- [ ] All utilities moved to scripts/lib/ and properly sourced
- [ ] Build pipeline tested and functional
- [ ] All documentation updated and accurate
- [ ] Python utilities have proper docstrings and comments
- [ ] ShellCheck passes for all modified shell scripts
- [ ] No functionality regressions

## Testing Checklist

Before marking Phase 3-5 complete:
- [ ] Run `./check-env.sh` - passes
- [ ] Run `./build.sh config.toml` with test config - succeeds
- [ ] Verify APKMirror download with Python parser - works
- [ ] Verify Uptodown download with Python parser - works
- [ ] Check all documentation links - valid
- [ ] Run ShellCheck on all shell scripts - passes
- [ ] Verify no lib/ references remain in codebase
- [ ] Confirm lxml installation instructions in README
