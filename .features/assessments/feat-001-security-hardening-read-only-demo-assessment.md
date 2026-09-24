# System Review: FEAT-001 — Security Hardening + Read-Only Mode

## Summary

- **Execution Report**: `.features/execution-reports/feat-001-security-hardening-read-only-demo.md`
- **Original Plan**: `.features/plans/feat-001-security-hardening-read-only-demo.md`
- **PRD Sections Analyzed**: none. **The repo has no PRD** (`references/PRD.md` does not exist). The requirements baseline used instead:
  - The user's request: fix review items 1–3 and 5, and make the container image read-only by default.
  - The pre-publication security review in this session.
  - `CLAUDE.md` conventions (Security, Storage, Error handling, Testing).
- **Assessment Date**: 2026-09-23

---

## Divergence Analysis

### Justified Divergences

#### Extracted `_convert_to_parquet` helper
- **Classification**: Justified — Better Approach
- **Description**: The format-specific COPY logic moved into a helper, so one `try/except duckdb.Error` covers conversion, metadata, view and upsert.
- **Benefit**: Shallower nesting, ruff line-length compliance, a single error-translation point.

#### Unknown-format check moved ahead of the write lock
- **Classification**: Justified — Better Approach
- **Description**: `ingest_file` rejects unsupported formats before acquiring the lock.
- **Benefit**: Fails fast and keeps the "unsupported format" message distinct from "could not read file".

#### Extra regression tests
- **Classification**: Justified — Better Approach
- **Description**: Added tests for an absolute-path upload, `0.0.0.0`, transport-error genericity, the public from-url happy path, and startup with a legacy invalid name.
- **Benefit**: Covers edge cases the plan listed in prose but didn't enumerate as tests.

### Unjustified Divergences

#### `fake_dns` fixture had to pass IP literals through
- **Classification**: Unjustified — Assumption Failure
- **Description**: The plan specified a fixture that "returns the given IP list" for every host. That would make `127.0.0.1` look public and silently hollow out the redirect-to-private test.
- **Root Cause**: The plan designed a test double without checking whether it preserved the security property under test.
- **Missing Information**: "Fake resolvers must resolve IP literals to themselves."
- **Source**: Reasoning about `validate_public_url` (it resolves every host, including literals).
- **Planning Step That Failed**: Phase 4 (Deep Strategic Thinking): "How will this be tested comprehensively?"

#### Builtins router: `UnsafeURLError` not in the 502 mapping
- **Classification**: Unjustified — Research Gap (minor)
- **Description**: `UnsafeURLError` subclasses `ValueError`. Left unmapped, it would fall into the router's `ValueError → 404 "unknown dataset"` branch.
- **Root Cause**: The plan listed two of the three `safe_fetch` exceptions.
- **Missing Information**: The full exception hierarchy of the new module when mapping it at call sites.
- **Source**: The plan's own Task 5 definitions.
- **Planning Step That Failed**: Phase 5 (Task consistency across tasks).

#### Streaming MockTransport requires an async iterator
- **Classification**: Unjustified — Research Gap (test-only)
- **Description**: The httpx `AsyncClient` asserts `AsyncByteStream`. A sync iterator body fails.
- **Root Cause**: The plan linked the MockTransport docs but didn't note the sync/async body distinction.
- **Planning Step That Failed**: Phase 3 (External Research, gotchas).

---

## Requirements Alignment (in place of PRD)

### Aligned
- **Item 1, upload traversal/injection**: the client filename is never used as a path. Uploads are `<uuid4hex><ext>`, and all SQL path literals go through `quote_literal`. Verified by tests and E2E curl.
- **Item 2, dataset-name injection**: `^[a-z][a-z0-9_]{0,62}$` is enforced at the schema (422), in the service (`validate_dataset_name`) and on startup (`reregister_views` skips legacy names).
- **Item 3, SSRF**: scheme allowlist, every resolved IP must be global, re-validation on each redirect hop, redirect cap and size cap. Verified against metadata, internal-network and localhost URLs.
- **Item 5, error leakage**: global handlers return generic bodies. `str(e)` is only returned for our own `ValueError` messages.
- **Item 4, read-only**: `READ_ONLY` dependency on ingest and delete, frontend hides controls, and the image defaults to `READ_ONLY=true`. Built-ins stay available and idempotent.
- **CLAUDE.md**: parameterized/structured SQL ✓, state only under DATA_DIR (now enforced by the DuckDB sandbox) ✓, no network in tests ✓, type hints ✓, ruff ✓, env-var config ✓.

### Misalignments
- **CLAUDE.md "Error handling: FastAPI exception handlers"**: this was only partially true before this feature (routers returned `str(e)`). It now matches. No update needed.
- **CLAUDE.md "Storage: never system temp dirs"**: Starlette/python-multipart still spool large multipart bodies to the system temp dir before the handler runs. This is pre-existing, not introduced here, and irrelevant in read-only production. Classification: CLAUDE.md is correct; it's a known residual gap.

---

## Residual Risks (non-blocking)

1. **DNS rebinding** in `safe_fetch`: accepted and documented. from-url is disabled in read-only production.
2. **Builtin idempotency check runs outside the write lock**: two simultaneous first loads could both download. Bounded (4 fixed datasets, size-capped), so harmless.
3. **Raw uploads are kept after conversion** (pre-existing behavior). They now have UUID names, so they accumulate without being overwritten. Only relevant in writable mode.
4. **Stored XSS in the frontend** (FEAT-002) is still open. Low risk while production is read-only and serves only Natural Earth data, but it must be fixed before any writable public deploy.

**No critical items affect this feature.**

---

## Recommendations

### PRD Updates Required

#### Update 1: Create a minimal PRD
- **Section**: new `references/PRD.md`
- **Content**: purpose (portfolio code sample, LAN-only deployment), deployment modes (read-only image default vs writable), supported formats, the security invariants listed under CLAUDE.md Additions below, and non-goals (multi-user auth).
- **Rationale**: the system-review command expects one. Without it, reviews fall back to chat history.

### plan-feature Command Improvements

#### Improvement 1: Test-double integrity check
- **Phase Affected**: Phase 4 (Strategic Thinking) → Testing Strategy
- **Current Behavior**: test doubles are specified by what they return.
- **Suggested Change**: for each security-relevant fake or mock, state which property it must *not* weaken, and add a test that fails if it does.
- **Would Have Caught**: the `fake_dns` IP-literal issue.

#### Improvement 2: Exception-hierarchy mapping table
- **Add Verification Step**: when a plan introduces new exception classes, include one table: exception → HTTP status → message source (ours or upstream), per call site.
- **Trigger**: any plan adding custom exceptions or error handlers.
- **Prevents**: the builtins `UnsafeURLError` → 404 mis-mapping.

### CLAUDE.md Additions

#### Addition 1: Security invariants
- **Section**: Key Technical Details
- **Content**:
```
- DuckDB is sandboxed to DATA_DIR (allowed_directories, enable_external_access=false, lock_configuration). Any new SET must run before `_apply_sandbox()`; all file I/O must stay under DATA_DIR.
- Dataset names must match `naming.DATASET_NAME_PATTERN`; never use a client-supplied filename as a filesystem path (use `new_upload_path`). Quote SQL path literals with `db.quote_literal`.
- Outbound HTTP for user-supplied URLs goes through `services/safe_fetch.download_to_file` only.
- Only `ValueError` messages we raise may be returned to clients; everything else goes to the generic handlers in `main.py`.
- `READ_ONLY=true` (image default) must block every mutating endpoint via `Depends(require_writable)`.
```
- **Prevents**: regressions that reopen items 1–5.

---

## Metrics

| Metric | Value |
|--------|-------|
| Total Divergences | 6 |
| Justified | 3 |
| Unjustified | 3 (all minor, caught during execution) |
| PRD Misalignments | n/a (no PRD); 1 pre-existing CLAUDE.md gap noted |
| Recommendations Generated | 4 |

### Planning Quality Score

**Score: 8.5/10**

Deductions:
- −0.5: test-double assumption (fake DNS)
- −0.5: incomplete exception mapping (builtins)
- −0.5: missing httpx async-stream gotcha

---

## Action Items

- [ ] Operator: set or confirm `READ_ONLY=true` on the live K8s deployment, then audit `_datasets` and `/data/uploads` for uploads made while endpoints were open.
- [ ] Operator: build the image in CI (Docker was unavailable locally) and smoke-test `/health` → `read_only: true`.
- [ ] Add the CLAUDE.md security invariants above.
- [ ] Next feature: FEAT-002 (frontend XSS) before any writable public deployment.
- [ ] Optional: create `references/PRD.md`; align `release.yml` with `ci.yml` (`ruff format --check`).
