# Execution Report: FEAT-001 — Security Hardening + Read-Only Public Demo

**Date:** 2026-09-23
**Branch:** `fix/feat-001-security-hardening`

## Meta Information

- **Plan file:** `.features/plans/feat-001-security-hardening-read-only-demo.md`
- **Files added:**
  - `src/geo_app/naming.py`
  - `src/geo_app/dependencies.py`
  - `src/geo_app/services/safe_fetch.py`
  - `tests/test_security.py`
- **Files modified:**
  - `pyproject.toml`, `Dockerfile`, `Makefile`, `README.md`
  - `src/geo_app/config.py`, `src/geo_app/db.py`, `src/geo_app/main.py`
  - `src/geo_app/models/schemas.py`
  - `src/geo_app/routers/{builtins,datasets,health,ingest,query}.py`
  - `src/geo_app/services/{builtin_datasets,ingestion}.py`
  - `src/geo_app/static/{app.js,index.html}`
  - `tests/conftest.py`
- **Lines changed (code, docs and tests, excluding `.features/`):** +839 −142 across 22 files

## Validation Results

- **Syntax & linting:** ✓ `ruff check src/ tests/` clean. `ruff format --check src/ tests/` clean. `node --check app.js` clean.
- **Type checking:** n/a. The project has no mypy or pyright (per plan). Type hints are on every new function signature.
- **Unit tests:** ✓ `tests/test_security.py` 56 passed. This covers naming, `quote_literal`, URL validation (14 cases) and downloader behavior (redirects, size caps, generic errors).
- **Integration tests:** ✓ full suite **74 passed** (18 pre-existing and 56 new), 0 failed.
- **Manual E2E (uvicorn + curl):** ✓
  - `READ_ONLY=true`:
    - health returns `read_only: true`
    - upload, from-url and delete → 403
    - list → 200
  - Writable:
    - Upload with filename `../../../pwn'x.geojson` → 200 as `pwn_x`, stored as `<uuid>.geojson`, with nothing written outside `uploads/`.
    - from-url to `169.254.169.254`, `10.0.0.5` and `localhost` → 400 `"URL host is not allowed"`.
    - Name injection → 422.
    - Unknown dataset → 404 `"Dataset or column not found"`.
    - Corrupt upload → 400 `"Could not read file as geojson"`, with no path in the response.
    - Delete → 200.
  - No tracebacks in the server logs.
- **Container build (Level 3):** ✗ **skipped.** The devcontainer user lacks permission on `/var/run/docker.sock`. The `ENV READ_ONLY=true` line is verified in the Dockerfile. CI builds the image.
- **Browser check of the hidden controls:** not performed (no browser here). Verified indirectly: `uploadSection` is served and the JS parses. The hide logic is 5 lines, reviewed by inspection.

## What Went Well

- The planning-time DuckDB sandbox experiment carried over unchanged. `allowed_directories` + `enable_external_access=false` + `lock_configuration` worked first time with spatial `ST_Read`, CSV and parquet, and no existing test needed changing.
- Pinning "no DuckDB exception subclasses `ValueError`" during planning made the error-handling rule simple and safe: `ValueError` messages are ours, everything else is generic.
- Putting the name rules in a separate `naming.py` avoided a `db.py` ↔ `ingestion.py` import cycle, as the plan predicted.
- All 18 pre-existing tests passed unchanged throughout.

## Challenges Encountered

- **`ruff format` changes line boundaries** after scripted edits. A second scripted replace missed a reformatted statement and briefly left an undefined `src` name, which ruff caught immediately.
- **`httpx.MockTransport` with `AsyncClient`** needs an *async* iterator for a streamed body. A sync `iter([...])` raises `AssertionError` inside httpx. Fixed in the test.
- **Fake DNS vs IP literals:** a naive fake resolver that returns a public IP for every host would also "resolve" `127.0.0.1` as public and hide the redirect-to-private bug. The fixture now passes IP literals through unchanged.

## Divergences from Plan

**Extracted a `_convert_to_parquet` helper in `ingestion.py`**
- Planned: wrap the existing `ingest_file` body's DuckDB work in `try/except duckdb.Error`.
- Actual: moved the format-specific COPY logic into `_convert_to_parquet(cur, fmt, file_path, parquet_path)`, and wrapped conversion, metadata, view and upsert in one `try`.
- Reason: keeps nesting shallow and lines ≤100 once `quote_literal(...)` is added. The behavior is identical.
- Type: Better approach found.

**`ingest_file` rejects unknown formats before taking the write lock**
- Planned: keep the `else: raise ValueError` inside the cursor block.
- Actual: checked up front, next to name validation.
- Reason: fail fast, and it's needed so the `duckdb.Error` wrapper isn't the thing reporting unsupported formats.
- Type: Better approach found.

**Builtins router also maps `UnsafeURLError` → 502**
- Planned: `DownloadError` / `DownloadTooLargeError` → 502.
- Actual: `UnsafeURLError` is included too.
- Reason: it subclasses `ValueError`, so it would otherwise be reported as a misleading 404 "unknown dataset".
- Type: Plan assumption wrong (minor).

**The `fake_dns` fixture passes IP literals through**
- Planned: "returns the given IP list."
- Actual: IP-literal hosts resolve to themselves; hostnames get the fake list.
- Reason: without this, the redirect-to-`127.0.0.1` test would pass for the wrong reason.
- Type: Plan assumption wrong.

**Extra tests beyond the plan**
- Added: upload with an absolute path, `0.0.0.0`, a transport-error message, a public from-url happy path through the real downloader with a mock transport, and startup with a legacy invalid name in `_datasets`.
- Type: Better approach found.

## Skipped Items

- **Level 3 `docker build`.** Reason: no Docker socket permission in the devcontainer. Mitigation: CI release workflow builds on push to `main`.
- **Visual browser check of the read-only UI.** Reason: no browser available. Mitigation: served HTML and JS syntax verified.

## Recommendations

- **Plan command:** when a plan proposes test doubles for security checks (fake DNS, mock transports), it should spell out that the double must not weaken the property under test (e.g. IP literals bypass fake DNS). Also note httpx's async-iterator requirement for streamed MockTransport bodies.
- **Execute command:** after any scripted multi-replace, run `ruff format` **before** further scripted edits, or use exact-match edits, so later replacements aren't silently skipped.
- **CLAUDE.md additions:**
  - "DuckDB is sandboxed to `DATA_DIR` (`allowed_directories`, external access off, config locked). New file reads/writes must stay under `DATA_DIR`, and any `SET` must happen before `_apply_sandbox()`."
  - "Dataset names must match `naming.DATASET_NAME_PATTERN`. Never use a client-supplied filename as a path."
  - "Don't return `str(e)` for non-`ValueError` exceptions. The global handlers in `main.py` return generic bodies."
- **CI:** `release.yml` runs lint and tests but not `ruff format --check` (ci.yml does). Worth aligning.
