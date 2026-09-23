# Feature List

## In Progress

## Backlog

- **FEAT-002** — Frontend stored XSS: `app.js` builds the dataset list and map popups with `innerHTML` / `setHTML` from dataset names and feature properties. Escape or switch to `textContent` / DOM construction. **Required before any writable public deployment.**
- **FEAT-003** — Devcontainer cleanup: rename leftover "SPD" project references in `.devcontainer/` and drop the commented-out `spd_user:spd_password` DATABASE_URL.
- **FEAT-004** — Secret scanning: add a gitleaks pre-commit hook and enable GitHub secret scanning and push protection when the repo goes public.
- **FEAT-005** — Auth for write endpoints (API key), if a writable public deployment is ever needed.
- **FEAT-006** — Add FEAT-001 security invariants to CLAUDE.md, create `references/PRD.md`, and add `ruff format --check` to `release.yml` (see FEAT-001 assessment).

## Done

- **FEAT-001** — Pre-publication security hardening: upload path traversal + SQL injection, dataset-name injection, SSRF on URL ingest, error-detail leakage, and a `READ_ONLY` mode for the public demo (image default). Also sandboxes DuckDB to `DATA_DIR`. Completed 2026-09-23 on branch `fix/feat-001-security-hardening`.
  - Plan: `.features/plans/feat-001-security-hardening-read-only-demo.md`
  - Report: `.features/execution-reports/feat-001-security-hardening-read-only-demo.md`
  - Assessment: `.features/assessments/feat-001-security-hardening-read-only-demo-assessment.md`
  - Open operator actions: confirm `READ_ONLY=true` on live K8s; audit `_datasets` and `/data/uploads`; CI image build (Docker unavailable locally).
