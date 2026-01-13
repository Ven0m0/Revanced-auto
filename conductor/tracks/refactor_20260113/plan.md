# Plan: Refactor Codebase & Clean Up Repo

## Phase 1: Structural Reorganization
- [x] Task: Create 'assets' and 'tests' directories and move relevant files [d04b50e]
- [ ] Task: Update .gitignore to reflect new asset locations
- [ ] Task: Conductor - User Manual Verification 'Phase 1: Structural Reorganization' (Protocol in workflow.md)

## Phase 2: Logic Centralization (Environment Checks)
- [ ] Task: Create lib/checks.sh and implement check_prerequisites
- [ ] Task: Refactor build.sh to use lib/checks.sh
- [ ] Task: Refactor check-env.sh to use lib/checks.sh
- [ ] Task: Verify environment checks still pass
- [ ] Task: Conductor - User Manual Verification 'Phase 2: Logic Centralization' (Protocol in workflow.md)

## Phase 3: Code Cleanup & Dependency Fixes
- [ ] Task: Remove deprecated toml_parse_table_to_array from lib/config.sh
- [ ] Task: Update lib/patching.sh to reference new asset paths
- [ ] Task: Improve aapt2 detection logic in lib/helpers.sh (Support system binary)
- [ ] Task: Conductor - User Manual Verification 'Phase 3: Code Cleanup & Dependency Fixes' (Protocol in workflow.md)
