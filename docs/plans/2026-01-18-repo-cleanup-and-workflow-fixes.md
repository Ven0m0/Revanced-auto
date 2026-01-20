# Repository Cleanup and Workflow Fixes Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Finalize html_parser.py, remove htmlq binaries and references, clean up unneeded files, validate all scripts work correctly, and fix GitHub workflows to ensure APK builds complete successfully.

**Architecture:**
- Replace deprecated htmlq binary with pure Python HTML parser (lxml + cssselect)
- Remove 16MB htmlq binary directory from repository to reduce size
- Audit and remove unneeded files (legacy docs, duplicate configs, unused test files)
- Validate bash scripts individually and when sourced together
- Fix GitHub workflow issues preventing successful APK builds (missing dependencies, incorrect paths, upload failures)

**Tech Stack:** Bash (scripts), Python 3.11+ (html_parser.py), GitHub Actions, lxml/cssselect

---

## Task 1: Finalize and Test html_parser.py

**Files:**
- Modify: `scripts/html_parser.py` (already exists, verify completeness)
- Modify: `pyproject.toml` (ensure lxml and cssselect are dependencies)
- Test: Direct Python execution with sample HTML

**Step 1: Verify html_parser.py has proper error handling**

Read `scripts/html_parser.py` and confirm it has:
- Type hints for all functions ✓
- Proper error handling for malformed HTML ✓
- Both `--text` and `--attribute` modes ✓
- Exit codes: 0 for success, 1 for no results, non-zero for errors ✓

Expected: File should be complete and ready to use.

**Step 2: Verify pyproject.toml has dependencies**

Check that `pyproject.toml` includes:
```toml
dependencies = [
    "lxml",
    "cssselect",
]
```

If missing, add them.

**Step 3: Test html_parser.py with sample HTML**

Run:
```bash
echo '<div class="version">1.2.3</div>' | python3 scripts/html_parser.py "div.version" --text
```

Expected output:
```
1.2.3
```

Run:
```bash
echo '<a href="/download/app.apk">Download</a>' | python3 scripts/html_parser.py "a" --attribute href
```

Expected output:
```
/download/app.apk
```

**Step 4: Test error cases**

Run:
```bash
echo '<invalid' | python3 scripts/html_parser.py "div" --text
```

Expected: Exit code 1, error message to stderr.

**Step 5: Commit**

```bash
git add scripts/html_parser.py pyproject.toml
git commit -m "test: verify html_parser.py and dependencies are complete"
```

---

## Task 2: Verify htmlq References Removed

**Files:**
- Search: All files in `scripts/lib/` and `scripts/`
- Verify: No binary calls to htmlq remain

**Step 1: Search for remaining htmlq references**

Run:
```bash
grep -r "htmlq" scripts/ --include="*.sh" 2>/dev/null
```

Expected: Only comments mentioning it (e.g., "htmlq" in comments about avoiding repeated calls). No executable references.

**Step 2: Search for references in main scripts**

Run:
```bash
grep -r "htmlq" . --include="*.sh" --exclude-dir=bin 2>/dev/null
```

Expected: No matches (or only in comments/documentation).

**Step 3: Verify download.sh uses python parser**

Read `scripts/lib/download.sh` and confirm it calls:
```bash
python3 scripts/html_parser.py --text "selector"
python3 scripts/html_parser.py --attribute attr "selector"
```

Not:
```bash
htmlq --text "selector"
```

**Step 4: Commit**

```bash
git add -A
git commit -m "chore: confirm htmlq references removed from scripts"
```

---

## Task 3: Remove htmlq Binaries

**Files:**
- Delete: `bin/htmlq/` (entire directory - 16MB savings)
- Verify: `.gitignore` doesn't need updates (binaries are already tracked)

**Step 1: Remove htmlq directory**

Run:
```bash
rm -rf bin/htmlq/
```

**Step 2: Verify removal**

Run:
```bash
ls -la bin/
```

Expected: `htmlq/` directory should not exist.

**Step 3: Check git status**

Run:
```bash
git status | grep htmlq
```

Expected: Shows deleted files.

**Step 4: Commit deletion**

```bash
git add -A
git commit -m "chore: remove deprecated htmlq binaries (16MB reduction)"
```

---

## Task 4: Audit and Remove Unneeded Files

**Files:**
- Audit: Root directory and `docs/` for unused files
- Delete: Files identified as unnecessary

**Step 1: Identify potentially unneeded files**

Run:
```bash
ls -lh | grep -E "\.txt|\.log|_old|_backup|\.tmp"
```

Check:
- `progress.txt` - Is this actively used in CI? Check git history.
- Any `*.bak` or `*.old` files

Also check `docs/`:
```bash
ls -lh docs/
```

**Step 2: Check git history for files**

For any suspicious files, run:
```bash
git log --follow --oneline docs/file.md | head -10
```

If not modified in last 50 commits, likely unneeded.

**Step 3: Remove identified files**

Example unneeded candidates:
- `progress.txt` (if not used by CI) - DELETE
- Old plan files in `docs/plans/` older than 6 months - DELETE
- Duplicate config files - DELETE
- `test-multi-source.sh` if superseded by proper test suite - REVIEW

Run:
```bash
git rm progress.txt  # if confirmed unneeded
```

**Step 4: Verify build still works**

After removing files, test:
```bash
bash -n build.sh  # syntax check
bash -c "source utils.sh && check_prerequisites"
```

Expected: No errors.

**Step 5: Commit deletions**

```bash
git add -A
git commit -m "chore: remove unneeded files (progress.txt, old docs)"
```

---

## Task 5: Validate All Scripts Individually

**Files:**
- Syntax check: All `.sh` files in `scripts/lib/`, `scripts/`, root
- Logic check: Source order and dependencies

**Step 1: Syntax check all shell scripts**

Run:
```bash
for f in scripts/lib/*.sh scripts/*.sh build.sh utils.sh check-env.sh extras.sh; do
  if [ -f "$f" ]; then
    bash -n "$f" && echo "✓ $f" || echo "✗ $f"
  fi
done
```

Expected: All show `✓`.

**Step 2: Check individual lib scripts can't be sourced alone (they should fail)**

Run:
```bash
bash -c "source scripts/lib/download.sh" 2>&1 | head -5
```

Expected: Should show error or warning about unset variables (expected - they need utils.sh first).

**Step 3: Verify utils.sh loads all modules correctly**

Run:
```bash
bash -c "source utils.sh" 2>&1
```

Expected: No errors.

**Step 4: Verify key functions exist after sourcing**

Run:
```bash
bash -c "source utils.sh && type log_info check_prerequisites toml_get scrape_text" 2>&1
```

Expected: Output shows all functions are defined.

**Step 5: Test a complete source + function call**

Run:
```bash
bash -c "
  source utils.sh
  log_info 'Test message'
"
```

Expected: Should print a cyan "Test message" line.

**Step 6: Commit**

```bash
git add -A
git commit -m "test: verify all shell scripts have valid syntax and dependencies"
```

---

## Task 6: Validate Scripts Work Combined in Build

**Files:**
- Test: Run against test config
- Verify: All modules work together

**Step 1: Check build.sh prerequisites without building**

Run:
```bash
bash build.sh --help 2>&1 || true
```

Or better, just check prerequisites:
```bash
bash -c "
  source utils.sh
  check_prerequisites
" 2>&1
```

Expected: Shows what's missing or succeeds.

**Step 2: Test config parsing**

Run:
```bash
bash -c "
  source utils.sh
  toml_prep config.toml
  echo 'Config loaded successfully'
" 2>&1
```

Expected: "Config loaded successfully" (or error with useful message).

**Step 3: Test that build.sh has no syntax errors**

Run:
```bash
bash -n build.sh && echo "Build script syntax OK"
```

Expected: "Build script syntax OK"

**Step 4: Test a dry-run (if supported) or check-mode**

If build.sh supports `--dry-run` or similar, use it:
```bash
./build.sh --dry-run config.toml 2>&1 | head -20
```

Otherwise just verify it loads:
```bash
bash -c "source build.sh" 2>&1 | head -5
```

**Step 5: Commit**

```bash
git add -A
git commit -m "test: verify build.sh and all modules work together"
```

---

## Task 7: Fix GitHub Workflows for Successful APK Builds

**Files:**
- Modify: `.github/workflows/build.yml`
- Modify: `.github/workflows/build-daily.yml`
- Check: `.github/workflows/build-manual.yml`
- Check: `.github/workflows/build-pr.yml`

**Step 1: Identify workflow issues**

Review `build.yml` line 71:
```yaml
- name: Install Python dependencies
  run: pip install -e .
```

This installs the project as editable. Verify `pyproject.toml` has all needed dependencies:
- lxml
- cssselect

Read `pyproject.toml` and confirm both are listed in `dependencies`.

**Step 2: Verify Python version matches project requirements**

Line 68 shows Python 3.11. Check `pyproject.toml`:
```toml
requires-python = ">=3.9"
```

Confirm 3.11 is compatible. If project needs 3.11+ specifically, document it.

**Step 3: Check artifact upload paths**

Line 92 in build.yml:
```yaml
path: ./build/*.apk
```

Verify `build.sh` actually outputs APKs to `build/` directory. Check script output format.

Run locally:
```bash
grep -n "mkdir.*build\|cp.*build/" build.sh scripts/lib/*.sh
```

Expected: Should show APKs are placed in `./build/` directory.

**Step 4: Verify artifact download in release job**

Lines 133-145 download artifacts. Verify the patterns match:
- `pattern: apks-*` should match upload names from line 91: `apks-${{ matrix.id }}`
- `pattern: build-log-*` should match line 98: `build-log-${{ matrix.id }}`

These look correct. Verify they're case-sensitive and match exactly.

**Step 5: Check build-daily.yml flow**

Line 40 runs:
```bash
./build.sh config.toml --config-update
```

Verify this flag exists in build.sh:

Run:
```bash
grep -n "\-\-config-update" build.sh
```

If not found, this will fail. Either:
- Add `--config-update` flag to build.sh, OR
- Remove this check from workflow

Check if this is implemented:
```bash
grep -A 5 "config-update" build.sh
```

**Step 6: Fix missing --config-update flag if needed**

If not implemented, modify `build.sh` to handle it. Add near line 62 (where config is loaded):

After finding where it's checked, add:
```bash
if [[ ${1-} == "--config-update" ]]; then
  source utils.sh
  # Logic to check if updates are available
  # Exit with appropriate code
fi
```

Or simplify by removing that check from workflow if not needed.

**Step 7: Verify build.sh outputs build log**

Check build.sh creates `build.md`. Run:
```bash
grep -n "build.md" build.sh scripts/lib/*.sh
```

Expected: Should see `build.md` being created.

**Step 8: Test workflow locally (optional)**

You can't fully test GitHub Actions locally, but verify the scripts work:
```bash
bash build.sh config.toml 2>&1 | tail -20
```

This won't build APKs without credentials, but will show if it starts correctly.

**Step 9: Update workflows if needed**

If `--config-update` is not implemented in build.sh, update `build-daily.yml` line 40:

Change from:
```bash
UPDATE_CFG=$(./build.sh config.toml --config-update)
```

To:
```bash
UPDATE_CFG=$(grep "patches-version\|cli-version" config.toml)
```

Or implement the flag properly in build.sh.

**Step 10: Commit workflow fixes**

```bash
git add .github/workflows/*.yml pyproject.toml build.sh
git commit -m "fix: update workflows and add missing build.sh config-update support"
```

---

## Task 8: Final Integration Test and Commit

**Files:**
- Verify: All changes work together
- Commit: Final comprehensive test

**Step 1: Run final syntax check on all scripts**

Run:
```bash
for f in scripts/lib/*.sh scripts/*.sh build.sh utils.sh check-env.sh extras.sh; do
  bash -n "$f" || { echo "FAILED: $f"; exit 1; }
done
echo "All scripts syntax check PASSED"
```

Expected: "All scripts syntax check PASSED"

**Step 2: Verify no htmlq references remain**

Run:
```bash
grep -r "bin/htmlq\|htmlq" . --exclude-dir=.git --exclude-dir=.github --exclude="*.md" 2>/dev/null | grep -v "comment\|Comment" || echo "No htmlq references found"
```

Expected: "No htmlq references found" or only comments.

**Step 3: Verify bin/ directory is smaller**

Run:
```bash
du -sh bin/
```

Expected: Should be significantly smaller than 16MB (htmlq was removed).

**Step 4: Verify pyproject.toml has dependencies**

Run:
```bash
grep -A 5 "dependencies" pyproject.toml
```

Expected: Shows lxml and cssselect listed.

**Step 5: Test html_parser.py one more time**

Run:
```bash
echo '<div class="test">Hello</div>' | python3 scripts/html_parser.py "div.test" --text
```

Expected: "Hello"

**Step 6: Create final commit**

```bash
git status
```

If there are uncommitted changes, add them:
```bash
git add -A
git commit -m "chore: repository cleanup - remove htmlq binaries, finalize html_parser, fix workflows

- Remove 16MB htmlq binary directory (now using pure Python parser)
- Finalize and test html_parser.py with lxml/cssselect
- Validate all shell scripts have correct syntax
- Verify script dependencies work when combined
- Fix GitHub workflow issues:
  - Ensure pyproject.toml has lxml/cssselect dependencies
  - Add missing --config-update flag to build.sh or simplify workflow logic
  - Verify artifact upload paths match expected outputs
- Remove unneeded files to reduce repository size"
```

**Step 7: Verify git log**

Run:
```bash
git log --oneline -10
```

Expected: Latest commits show the work completed.

**Step 8: Create summary**

Run:
```bash
echo "Repository cleanup complete:
- htmlq binaries removed (16MB savings)
- html_parser.py finalized with full testing
- All shell scripts validated
- GitHub workflows fixed
- Build should now succeed in CI"
```

---

## Validation Checklist

Before considering this complete:

- [ ] html_parser.py works with `--text` and `--attribute` flags
- [ ] No references to `htmlq` binary remain in scripts
- [ ] `bin/htmlq/` directory deleted
- [ ] All `.sh` files pass `bash -n` syntax check
- [ ] `utils.sh` sources all modules without errors
- [ ] `build.sh` loads without errors
- [ ] `pyproject.toml` lists lxml and cssselect dependencies
- [ ] GitHub workflow uses `pip install -e .` to get dependencies
- [ ] `build.sh` handles `--config-update` flag (or workflow updated)
- [ ] All commits are atomic and well-described
- [ ] Repository is smaller (htmlq binary removed)
- [ ] No uncommitted changes remain

---

## Execution Notes

**Do NOT:**
- Delete files without checking git history first
- Modify workflows without testing the scripts they call
- Skip testing individual scripts in isolation

**DO:**
- Commit frequently (each task = one commit)
- Test after each major change
- Verify dependencies are installed in CI (pyproject.toml)
- Check that workflow paths match actual output locations
