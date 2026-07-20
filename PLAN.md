# Implementation Plan

> **Status**: Updated 2026-07-18
> **Purpose**: Handoff-ready implementation plan
> **Source**: Derived from TODO.md + codebase inspection + comparison against krvstek/uni-apks and RookieEnough/Morphe-AutoBuilds

---

## Executive Summary

TODO.md asked to review [krvstek/uni-apks](https://github.com/krvstek/uni-apks) and [RookieEnough/Morphe-AutoBuilds](https://github.com/RookieEnough/Morphe-AutoBuilds) for Python and workflow patterns to port in. Both repos were inspected and cross-checked against this codebase's actual state (not assumptions). Most of what those repos do — scraper abstraction, retry/backoff, file-locked atomic downloads, sha256 verification, aria2c acceleration, matrix builds, draft-then-publish releases with cleanup, keystore password handled via `env:` indirection — this repo already has, often more robust. Two concrete, verified gaps remain.

## Verified Already Equivalent or Better (No Action)

| uni-apks / Morphe-AutoBuilds pattern | This repo's equivalent |
|---|---|
| Retry with backoff, atomic temp-file download | `scripts/utils/network.py`: `HttpClient._retry_with_backoff`, `download_with_lock` (flock + atomic `replace` + sha256 verify) |
| Multi-source scraper failover | `scripts/scrapers/download_manager.py`: tries sources in order, aggregates errors |
| Draft-release-then-publish, artifact existence check | `.github/workflows/build.yml` `release` job: `check_artifacts` gate before publishing |
| Release cleanup | `build.yml`: keeps latest 3 + current month releases |
| Config-hash-keyed caching | `build.yml`: `actions/cache` keyed on `hashFiles('config.toml')`; `setup-environment` action caches Android build-tools |
| Keystore password redaction | `patcher.py` passes secrets via `RV_KEYSTORE_PASSWORD` env var + `--keystore-password=env:RV_KEYSTORE_PASSWORD` (never on CLI/logged) |
| Bounded retry on downloads | `download_with_lock` retries via `HttpClient` config (`DEFAULT_MAX_RETRIES = 4`) |

---

## Phase 1: Wire existing version-check into the build matrix (incremental builds)

### Context
`scripts/version_tracker.py` already implements a `check` command that diffs current CLI/patches/app versions against `.github/last_built_versions.json`, but nothing calls it before building. `scripts/generate_matrix.sh` (used by `build.yml`'s `setup_matrix` job) unconditionally includes every `enabled = true` app, so scheduled builds rebuild everything daily even when nothing changed — the exact waste Morphe-AutoBuilds' incremental-matrix design avoids. The tracker to do the diff already exists here; it's just not consulted.

### Implementation Steps

**T1.1** Add a `--matrix` mode (or reuse `check`) to `scripts/version_tracker.py` that outputs the set of app keys with a version change, as JSON.

**T1.2** Update `scripts/generate_matrix.sh` to call it: default to only apps flagged as changed; on `workflow_dispatch` with a new `full_rebuild: true` boolean input (or if `.github/last_built_versions.json` is missing), fall back to the full enabled-app list.

**T1.3** Add `full_rebuild` as a `workflow_dispatch` input on `build.yml` / `build-manual.yml`, threaded through to `generate_matrix.sh`.

### Validation
```bash
uv run python -m pytest tests/test_version_tracker.py -v
./scripts/generate_matrix.sh   # confirm valid matrix JSON, full and incremental paths
```

---

## Phase 2: Status-code-aware retry in `HttpClient`

### Context
`HttpClient._retry_with_backoff` / `_async_retry_with_backoff` (`scripts/utils/network.py`) retry on *any* `httpx.HTTPError`, including 404s that will never succeed on retry — wasting the full backoff window (2s, 4s, 8s, 16s by default) on a request that's already known to be dead. uni-apks' `NetworkManager` distinguishes: 404 fails immediately, 403/5xx retry, other 4xx fail immediately. `HttpClient` doesn't currently raise for non-2xx (no `raise_for_status()` call visible in `_do_request`), so this needs the status check added, not just reordering.

### Implementation Steps

**T2.1** In `_do_request`/`_async_do_request`, call `response.raise_for_status()` before returning, so HTTP error codes surface as exceptions instead of silently returning error-page content.

**T2.2** In `_retry_with_backoff`/`_async_retry_with_backoff`, on `httpx.HTTPStatusError`, inspect `e.response.status_code`: 404 or other non-{403,5xx} 4xx → re-raise immediately (no retry); 403/5xx → keep existing backoff loop. Non-status errors (timeouts, connection errors) keep retrying as today.

### Validation
```bash
uv run python -m pytest tests/test_network.py -v
```

---

## Success Criteria

- [ ] `generate_matrix.sh` skips apps with unchanged versions by default; `full_rebuild` input forces the full set
- [ ] `HttpClient` fails fast on 404/4xx instead of exhausting retries
- [ ] `pytest tests/test_version_tracker.py tests/test_network.py` passes
