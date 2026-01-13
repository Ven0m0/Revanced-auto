# Plan: Refactor Codebase & Clean Up Repo

## Phase 1: Structural Reorganization
- [x] Task: Create 'assets' and 'tests' directories and move relevant files [d04b50e]
- [x] Task: Update .gitignore to reflect new asset locations [fd902cf]
- [x] Task: Conductor - User Manual Verification 'Phase 1: Structural Reorganization' (Protocol in workflow.md) [checkpoint: aeea6f4]

## Phase 2: Logic Centralization (Environment Checks)
- [x] Task: Create lib/checks.sh and implement check_prerequisites [9d7b603]
- [x] Task: Refactor build.sh to use lib/checks.sh [9d7b603]
- [x] Task: Refactor check-env.sh to use lib/checks.sh [85a5b0b]
- [x] Task: Verify environment checks still pass [6d021b6]
- [x] Task: Conductor - User Manual Verification 'Phase 2: Logic Centralization' (Protocol in workflow.md) [checkpoint: 520063a]

## Phase 3: Code Cleanup & Dependency Fixes
- [x] Task: Remove deprecated toml_parse_table_to_array from lib/config.sh [6c3c8d1]
- [x] Task: Update lib/patching.sh to reference new asset paths [c79a075]
- [~] Task: Improve aapt2 detection logic in lib/helpers.sh (Support system binary)
- [ ] Task: Clean up repository and remove garbage/leftover files
- [ ] Task: Conductor - User Manual Verification 'Phase 3: Code Cleanup & Dependency Fixes' (Protocol in workflow.md)

## Phase 4: Python Migration & Script Consolidation
- [ ] Task: Replace htmlq with Python HTML parsing implementation
- [ ] Task: Merge and deduplicate lib/ into scripts/ where appropriate
- [ ] Task: Update all references to moved/refactored utilities
- [ ] Task: Test build pipeline with Python-based HTML parsing
- [ ] Task: Conductor - User Manual Verification 'Phase 4: Python Migration & Script Consolidation' (Protocol in workflow.md)

## Phase 5: Documentation Enhancement
- [ ] Task: Update CLAUDE.md with architectural changes
- [ ] Task: Update CONFIG.md with new paths and utilities
- [ ] Task: Update README.md with dependency changes
- [ ] Task: Create/update developer documentation for new Python utilities
- [ ] Task: Document lib/ and scripts/ organization patterns
- [ ] Task: Conductor - User Manual Verification 'Phase 5: Documentation Enhancement' (Protocol in workflow.md)
