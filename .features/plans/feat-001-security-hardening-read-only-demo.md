# Feature: FEAT-001 — Security Hardening + Read-Only Public Demo

**Created:** 2026-09-23 at 18:40 UTC
**Plan Version:** 1.0
**Estimated Completion Time:** 4-6 hours

The following plan should be complete, but validate documentation and codebase patterns and task sanity before you start implementing. Pay special attention to naming of existing utils, types and models, and import from the right files.

## Feature Description

Close the vulnerabilities found in the pre-publication security review before `duckdb-geo-demo` goes public on GitHub. Fixes: (1) upload path traversal and SQL injection via the uploaded filename, (2) SQL injection via the user-supplied dataset `name`, (3) SSRF (server-side request forgery) in `/api/ingest/from-url`, and (5) internal exception text returned to clients. Item (4), unauthenticated writes, is addressed with a `READ_ONLY` mode that the public deployment runs in. As defense in depth, the DuckDB connection is also sandboxed to `DATA_DIR`.

## User Story

As the operator of a public portfolio demo
I want the app's write paths to be injection-proof and the public deployment to be read-only
So that publishing the source doesn't hand anyone a working exploit against the live site or its internal network

## Feature Metadata

**Feature Type**: Bug Fix (security)
**Estimated Complexity**: Medium
**Primary Systems Affected**: config, db, ingestion service, ingest/datasets/query/builtins/health routers, main app factory, static frontend, Dockerfile, README
**Dependencies**: none new. Raise the `duckdb` floor to `>=1.5.0` (sandbox settings were verified on 1.5.0).

---

## CONTEXT REFERENCES

### Relevant Codebase Files — YOU MUST READ THESE BEFORE IMPLEMENTING

- `CLAUDE.md` — conventions: type hints on all functions, ruff, pydantic-settings/env config, state only under DATA_DIR, no network in tests, parameterized SQL.
- `src/geo_app/config.py` (all) — `Settings`; add fields here.
- `src/geo_app/db.py` (16-49) — `initialize()` builds SQL with an f-string for `extension_directory`. `reregister_views()` interpolates stored names and paths.
- `src/geo_app/services/ingestion.py` (25-29 `sanitize_name`, 45-125 `ingest_file`, 128-163 `_extract_metadata`) — every `'{file_path}'` / `'{parquet_path}'` / `"{name}"` interpolation is a sink.
- `src/geo_app/routers/ingest.py` (12-67) — **VULN 1**: line 19 `settings.upload_dir / file.filename`. **VULN 2**: line 43 `body.name` is used unsanitized. **VULN 3**: lines 49-53 fetch any URL with `follow_redirects=True`. **VULN 5**: lines 31, 54, 64 return `str(e)`.
- `src/geo_app/services/spatial_query.py` (17-21) — `_validate_identifier`. It stays as is: it's also used for column names, which may be uppercase (Natural Earth `NAME`).
- `src/geo_app/routers/query.py` (27-67), `src/geo_app/routers/builtins.py` (18-23) — the `except Exception → HTTPException(500, str(e))` pattern to remove.
- `src/geo_app/routers/datasets.py` (134-155) — DELETE route, which needs the read-only guard.
- `src/geo_app/services/builtin_datasets.py` (57-85) — fixed-catalog downloader. It should reuse the new safe downloader.
- `src/geo_app/routers/health.py` — add `read_only` to the response.
- `src/geo_app/main.py` (31-55) — `create_app`; register exception handlers here.
- `src/geo_app/static/index.html` (18-22), `src/geo_app/static/app.js` (64-117, 203-212) — upload section and delete buttons to hide in read-only mode.
- `tests/conftest.py` — fixture pattern: `settings(data_dir)` → `create_app(settings)` → `TestClient` context manager.
- `tests/test_ingest.py` — the existing upload-test pattern `files={"file": (filename, fh)}`.

### New Files to Create

- `src/geo_app/naming.py` — dataset-name rules (no internal imports, so both `db.py` and the services can use it without circular imports).
- `src/geo_app/dependencies.py` — `require_writable` FastAPI dependency.
- `src/geo_app/services/safe_fetch.py` — SSRF-safe, size-capped downloader.
- `tests/test_security.py` — regression tests for every vulnerability above.

### Relevant Documentation — READ BEFORE IMPLEMENTING

- [DuckDB Securing DuckDB](https://duckdb.org/docs/stable/operations_manual/securing_duckdb/overview) — `enable_external_access`, `allowed_directories`, `lock_configuration`.
- [httpx Transports / MockTransport](https://www.python-httpx.org/advanced/transports/#mock-transports) — for network-free download tests.
- [httpx Streaming responses](https://www.python-httpx.org/quickstart/#streaming-responses) — `client.stream(...)` + `aiter_bytes()`.
- [FastAPI Handling Errors — install custom exception handlers](https://fastapi.tiangolo.com/tutorial/handling-errors/#install-custom-exception-handlers)
- [FastAPI Dependencies in path operation decorators](https://fastapi.tiangolo.com/tutorial/dependencies/dependencies-in-path-operation-decorators/) and [APIRouter `dependencies=`](https://fastapi.tiangolo.com/tutorial/bigger-applications/#another-module-with-apirouter)
- Python `ipaddress` — `is_global`, `is_multicast`, `IPv6Address.ipv4_mapped`.

### Verified facts (checked during planning; environment: Python 3.11.2, duckdb 1.5.0, httpx 0.28.1, fastapi 0.135.1, starlette 0.52.1, ruff 0.15.5)

- After `INSTALL/LOAD spatial`, running `SET allowed_directories = ?` (param `[data_dir + "/"]`), then `SET enable_external_access = false`, then `SET lock_configuration = true` gives these results:
  - **Still allowed:** `ST_Read`, `read_parquet`, CSV scans and `COPY ... TO` inside data_dir.
  - **Blocked** with `duckdb.PermissionException`: `ST_Read` outside data_dir, `../` traversal, `read_text('/etc/passwd')`, `COPY` to outside paths, `http://` reads.
  - Re-enabling the setting afterwards is rejected.
- No `duckdb` exception subclasses `ValueError`. `CatalogException` and `BinderException` are `ProgrammingError` → `DatabaseError` → `duckdb.Error`. So `except ValueError: detail=str(e)` never exposes DuckDB internals.
- Starlette's `ServerErrorMiddleware` **re-raises** after running an `Exception`/500 handler. Tests that assert a 500 response body must use `TestClient(app, raise_server_exceptions=False)`.
- Baseline: `pytest -q` → 18 passed.

---

## STEP-BY-STEP TASKS

Execute every task in order, top to bottom.

### Task 1: UPDATE `pyproject.toml`

- **IMPLEMENT**: `duckdb>=1.5.0`.
- **VALIDATE**: `pip install -e ".[dev]" -q && python -c "import duckdb; assert tuple(map(int, duckdb.__version__.split('.')[:2])) >= (1, 5)"`

### Task 2: UPDATE `src/geo_app/config.py`

- **IMPLEMENT**: Add `read_only: bool = False` (env `READ_ONLY`) and `max_upload_mb: int = Field(default=100, gt=0)` (env `MAX_UPLOAD_MB`). Add a `max_upload_bytes` property. Add a `field_validator("data_dir")` that returns `Path(v).resolve()`, so every path handed to DuckDB is absolute and matches `allowed_directories`.
- **GOTCHA**: Keep the default `read_only=False`, so local dev and the existing tests stay writable. The container image sets it to true (Task 14).
- **VALIDATE**: `python -c "from geo_app.config import Settings; s=Settings(data_dir='rel'); assert s.data_dir.is_absolute() and s.read_only is False and s.max_upload_bytes==100*1024*1024"`

### Task 3: CREATE `src/geo_app/naming.py`

- **IMPLEMENT**: dataset-name rules.
- **FUNCTIONS/EXPORTS**:
  - `DATASET_NAME_PATTERN = r"^[a-z][a-z0-9_]{0,62}$"`
  - `is_valid_dataset_name(name: str) -> bool`
  - `validate_dataset_name(name: str) -> str` (raises `ValueError("Invalid dataset name: must match ...")`)
  - `sanitize_name(name: str) -> str` (moved from `ingestion.py`)
- **KEY LOGIC**: `sanitize_name` keeps its existing behavior (stem → `[^a-zA-Z0-9_]`→`_` → collapse → strip → lower → fallback `"dataset"`), then prefixes `ds_` if the first char isn't a letter and truncates to 63 chars. Its output must always pass `validate_dataset_name`. The leading-letter rule also stops users from colliding with the internal `_datasets` / `_csv_import` tables.
- **GOTCHA**: Don't use `str.isalnum()`: it accepts Unicode letters. Use `re.fullmatch` with the ASCII pattern.
- **VALIDATE**: `python -c "from geo_app.naming import *; assert sanitize_name('2024.csv')=='ds_2024'; assert sanitize_name(\"a'b.geojson\")=='a_b'; assert sanitize_name('../../x.geojson')=='x'; assert not is_valid_dataset_name('_datasets')"`

### Task 4: UPDATE `src/geo_app/db.py`

- **ADD**: `quote_literal(value: str | Path) -> str`. It returns `"'" + str(value).replace("'", "''") + "'"`. Use it for **every** remaining SQL string literal holding a path, as a second layer behind server-generated paths.
- **UPDATE** `initialize()`:
  1. `SET extension_directory = {quote_literal(ext_dir)}`
  2. `INSTALL`/`LOAD spatial` (unchanged)
  3. `_init_metadata_table()`
  4. then the sandbox: `SET allowed_directories = ?` with `[str(data_dir) + "/"]`, `SET enable_external_access = false`, `SET lock_configuration = true`.
- **UPDATE** `reregister_views()`: skip rows where `not is_valid_dataset_name(name)` (log a warning with `logging.getLogger(__name__)`). The live PVC may hold names created before this fix. Use `quote_literal(parquet_path)`.
- **GOTCHA**: Sandbox must come **after** `INSTALL`/`LOAD spatial` (external access blocks extension install/load). The trailing `/` on the allowed dir matters: it stops `/data` from also allowing `/data-other`.
- **VALIDATE**: `ruff check src/geo_app/db.py && pytest tests/test_health.py -q`

### Task 5: CREATE `src/geo_app/services/safe_fetch.py`

- **IMPLEMENT**: SSRF-safe, size-capped HTTP download.
- **FUNCTIONS/EXPORTS**:
  - `class UnsafeURLError(ValueError)`, `class DownloadError(ValueError)`, `class DownloadTooLargeError(ValueError)`
  - `MAX_REDIRECTS = 5`
  - `async def _resolve(host: str, port: int) -> list[str]` — thin wrapper over `loop.getaddrinfo`, returning IP strings. This is the single seam tests monkeypatch.
  - `async def validate_public_url(url: str) -> None`
  - `async def download_to_file(url: str, dest: Path, max_bytes: int, *, transport: httpx.AsyncBaseTransport | None = None) -> None`
- **KEY LOGIC**:
  - **`validate_public_url`**: scheme ∈ {http, https}; hostname required; resolve with `asyncio.get_running_loop().getaddrinfo(host, port)`. Reject if **any** resolved address fails the check `ip.is_global and not ip.is_multicast`, after unwrapping `IPv6Address.ipv4_mapped`. This blocks 10/8, 172.16/12, 192.168/16, 127/8, 169.254/16 (cloud metadata), 100.64/10, ::1, fc00::/7 and similar. A resolution failure raises `UnsafeURLError`.
  - **`download_to_file`**: `httpx.AsyncClient(follow_redirects=False, timeout=60, transport=transport, headers={"User-Agent": "duckdb-geo-demo/0.1.0"})`.
    - Loop at most `MAX_REDIRECTS + 1` times: validate the URL, then `client.stream("GET", url)`. On 3xx with a `Location` header, set `url = str(resp.url.join(location))` and continue.
    - Non-2xx → `DownloadError(f"Download failed: remote returned HTTP {status}")`.
    - Reject early if `Content-Length` > max. Otherwise stream `aiter_bytes()` into `dest`, counting bytes, and raise `DownloadTooLargeError` once over max.
    - `httpx.HTTPError` → `DownloadError("Download failed")` with no exception text.
    - On any exception, `dest.unlink(missing_ok=True)` and re-raise.
- **GOTCHA**: Residual DNS-rebinding TOCTOU (check and connect resolve separately) is accepted. Document it in a module docstring line. The public deployment is read-only, so this endpoint is disabled there anyway. Never include the exception text or the resolved IP in error messages: they would turn the endpoint into a port scanner.
- **VALIDATE**: `ruff check src/geo_app/services/safe_fetch.py && python -c "import geo_app.services.safe_fetch"`

### Task 6: UPDATE `src/geo_app/services/ingestion.py`

- **REMOVE** the local `sanitize_name`; import it from `geo_app.naming` (keep it importable from `ingestion` for existing callers, or update `routers/ingest.py` in Task 9).
- **ADD** `new_upload_path(settings: Settings, original_filename: str) -> Path`: `fmt = detect_format(original_filename)`; raise `ValueError(f"Unsupported format: {suffix}")` if `"unknown"`; return `settings.upload_dir / f"{uuid4().hex}{Path(original_filename).suffix.lower()}"`. The client filename is never used as a path.
- **UPDATE** `ingest_file`:
  - `name = validate_dataset_name(dataset_name or sanitize_name(original_filename))` as the first line.
  - Store `Path(original_filename).name[:255]` as metadata.
  - Replace every `'{file_path}'` / `'{parquet_path}'` with `{quote_literal(...)}` (lines 59-60, 65-66, 70, 81, 85, 96, 131, 136, 144, 153).
  - Wrap the whole `with db.write_cursor()` block's DuckDB work so that `duckdb.Error` → `raise ValueError(f"Could not read file as {fmt}") from None`.
- **GOTCHA**: The CSV `ST_Point("{lon_col}", "{lat_col}")` identifiers are safe: they only match fixed sets `LAT_NAMES`/`LON_NAMES`. Leave them unchanged. `_extract_metadata`'s internal `try/except Exception: pass` stays.
- **VALIDATE**: `pytest tests/test_ingest.py -q`

### Task 7: CREATE `src/geo_app/dependencies.py`

- **IMPLEMENT**: `def require_writable(request: Request) -> None`. It raises `HTTPException(status_code=403, detail="This deployment is read-only")` when `request.app.state.settings.read_only`.
- **VALIDATE**: `python -c "import geo_app.dependencies"`

### Task 8: UPDATE `src/geo_app/models/schemas.py`

- **UPDATE** `IngestFromURLRequest`: `url: str = Field(max_length=2048)`, `name: str | None = Field(default=None, pattern=DATASET_NAME_PATTERN)` (import from `geo_app.naming`). Invalid names are rejected with 422 before reaching SQL.
- **VALIDATE**: `python -c "import pydantic, pytest; from geo_app.models.schemas import IngestFromURLRequest as R; R(url='http://x', name='ok_1'); pytest.raises(pydantic.ValidationError, R, url='http://x', name='x; DROP TABLE _datasets')"`

### Task 9: UPDATE `src/geo_app/routers/ingest.py`

- **UPDATE** the router: `APIRouter(prefix="/api/ingest", tags=["ingest"], dependencies=[Depends(require_writable)])`.
- **UPDATE** `upload_file`:
  - Compute `upload_path = new_upload_path(settings, file.filename)` (`ValueError` → 400) **before** reading.
  - Copy in 1 MiB chunks with `await file.read(CHUNK)`. Past `settings.max_upload_bytes`, delete the partial file and raise 413 `"File exceeds MAX_UPLOAD_MB"`.
  - Call `ingest_file(..., original_filename=file.filename)`. Catch only `ValueError` → 400 `str(e)`. Let anything else reach the global handler.
- **UPDATE** `ingest_from_url`:
  - `filename = Path(urlparse(body.url).path).name or "download"`; `name = body.name or sanitize_name(filename)`; `dest = new_upload_path(settings, filename)` (unknown extension → 400).
  - `await download_to_file(body.url, dest, settings.max_upload_bytes)`. Map `DownloadTooLargeError` → 413, and `UnsafeURLError`/`DownloadError` → 400 with `str(e)` (those messages are ours).
  - Then ingest, with the same `ValueError` handling as upload.
- **REMOVE**: `import httpx`, all `except Exception`, and `detail=f"Download failed: {e}"`.
- **GOTCHA**: `UploadFile.filename` is fully client-controlled (`../../x`, `/abs`, `a'b`). After this task it's only used for the extension and the metadata string. Starlette has already spooled the body to a temp file before the handler runs. That was already the case, and read-only production disables the route.
- **VALIDATE**: `pytest tests/test_ingest.py -q`

### Task 10: UPDATE `src/geo_app/routers/datasets.py`

- **ADD** `dependencies=[Depends(require_writable)]` to `@router.delete("/{name}")`.
- **UPDATE** the delete and geojson routes: reject invalid names with `is_valid_dataset_name`, returning 400 before any query. Keep the existing 404 path for valid-but-missing names.
- **VALIDATE**: `pytest tests/test_ingest.py::test_delete_dataset -q`

### Task 11: UPDATE `src/geo_app/services/builtin_datasets.py` and `src/geo_app/routers/builtins.py`

- **UPDATE** `load_builtin`:
  - First, if `_datasets` already has the target name and `parquet_dir/{name}.parquet` exists, return the stored metadata in the same dict shape as `ingest_file` and don't download. This keeps the builtin loader idempotent, so repeated public clicks can't be used to drive bandwidth or disk use.
  - Otherwise download with `download_to_file(builtin.url, download_path, settings.max_upload_bytes)` in place of the raw `httpx` call.
- **KEY LOGIC**: `/api/builtins/load` stays available in read-only mode. It only fetches the 4 hardcoded Natural Earth URLs into fixed names, and the public demo needs it to show data.
- **UPDATE** the router: keep `ValueError` → 404 for an unknown id. For `DownloadError`/`DownloadTooLargeError` (subclasses of `ValueError`, so catch them first) → 502 `"Failed to fetch built-in dataset"`. **REMOVE** `except Exception → 500 str(e)`.
- **VALIDATE**: `pytest tests/test_builtin_datasets.py -q`

### Task 12: UPDATE `src/geo_app/routers/query.py`

- **REMOVE** the four `except Exception as e: raise HTTPException(status_code=500, detail=str(e))` blocks. Keep `except ValueError` → 400 (messages come from `spatial_query.py`).
- **VALIDATE**: `pytest tests/test_query.py -q`

### Task 13: UPDATE `src/geo_app/main.py`

- **ADD** structured exception handlers in `create_app`, all returning `JSONResponse({"detail": ...})`:
  - `duckdb.CatalogException` → 404 `"Dataset or column not found"`
  - `duckdb.BinderException` → 400 `"Invalid query for this dataset"`
  - `duckdb.Error` → 500 `"Internal server error"` (log with `logger.exception`)
  - `Exception` → 500 `"Internal server error"` (log with `logger.exception`)
- **ADD** `logger = logging.getLogger(__name__)`.
- **GOTCHA**: Register the specific DuckDB subclasses before `duckdb.Error`. Starlette resolves handlers by MRO, so order is safe either way, but it reads clearer. Handlers must be plain `def` or `async def (request: Request, exc: X) -> JSONResponse` with type hints.
- **VALIDATE**: `pytest -q`

### Task 14: UPDATE `src/geo_app/routers/health.py`, the frontend, `Dockerfile`, `Makefile`, `README.md`

- **health.py**: add `"read_only": request.app.state.settings.read_only` to the response.
- **index.html**: give the Upload section `id="uploadSection"`.
- **app.js**: add `let readOnly = false;`. On startup, `fetch('/health')` and set `readOnly`; if true, `document.getElementById('uploadSection').hidden = true`. In `refreshDatasets`, only render the delete button when `!readOnly`. Keep the no-build vanilla-JS style.
- **Dockerfile**: add `ENV READ_ONLY=true` next to `ENV DATA_DIR=/data`, so the published image is read-only by default.
- **Makefile**: `run:` adds `-e READ_ONLY=false`, so the local container stays usable. `dev` is unchanged (defaults to writable).
- **README.md**: document `READ_ONLY` (default false; image default true) and `MAX_UPLOAD_MB` (default 100). State that the public demo runs read-only and that only built-in datasets can be loaded there.
- **VALIDATE**: `pytest tests/test_health.py -q && grep -q 'READ_ONLY=true' Dockerfile`

### Task 15: UPDATE `tests/conftest.py` and CREATE `tests/test_security.py`

- **conftest ADD**:
  - `readonly_app` fixture: `Settings(data_dir=data_dir, read_only=True)` → TestClient.
  - `app_no_raise` fixture: same as `app`, but `TestClient(application, raise_server_exceptions=False)`.
  - `fake_dns(monkeypatch)` fixture: returns a setter that monkeypatches `geo_app.services.safe_fetch._resolve` to return the given IP list.
- **test_security.py**: see the Testing Strategy below.
- **VALIDATE**: `pytest tests/test_security.py -v`

---

## TESTING STRATEGY

pytest with `tmp_path` fixtures and **no network** (CLAUDE.md). There is no pytest-asyncio, so call async helpers with `asyncio.run(...)` inside sync tests. Use `httpx.MockTransport` for downloads and monkeypatch `_resolve` for DNS.

### Unit tests (`tests/test_security.py`)

- **naming**: `sanitize_name` for `2024.csv`, `a'b.geojson`, `../../x.geojson`, a 200-char name (≤63) and `"'"` (→ `dataset`). `validate_dataset_name` rejects `_datasets`, `A`, `x"y`, `""`.
- **quote_literal**: `quote_literal("a'b") == "'a''b'"`.
- **validate_public_url** rejects:
  - `file:///etc/passwd`, `ftp://x/y`, `http:///nohost`
  - `http://127.0.0.1/`, `http://10.0.0.5/internal`, `http://169.254.169.254/latest/meta-data`
  - `http://[::1]/`, `http://[::ffff:127.0.0.1]/`, `http://100.64.0.1/`
  - a hostname whose fake DNS resolves to `192.168.1.5`
  - a hostname whose fake DNS resolves to both `93.184.216.34` and `10.0.0.1` (any private address fails)
- **validate_public_url** accepts a hostname resolving only to `93.184.216.34`.
- **download_to_file**, using a MockTransport with public fake DNS:
  - 200 with a small body → file written.
  - 302 → `http://127.0.0.1/` → `UnsafeURLError`, dest not created.
  - More than 5 redirects → `DownloadError`.
  - Body over `max_bytes` with no Content-Length → `DownloadTooLargeError`, partial file removed.
  - 404 → `DownloadError` whose message contains `404` and nothing else from the server.

### Integration tests (TestClient)

- **Upload path traversal**: upload `("../../evil.geojson", sample)` → 200, dataset `evil`. Assert no `evil.geojson` in `data_dir.parent` or `data_dir`, and every file in `upload_dir` has a 32-hex-char stem.
- **Upload quote injection**: `("a'b.geojson", sample)` → 200, dataset `a_b`, `GET /api/datasets/a_b` 200.
- **Upload unknown extension**: `evil.sh` → 400, and nothing is written to `upload_dir`.
- **Upload size cap**: Settings with `max_upload_mb=1`, 1.5 MB body → 413, `upload_dir` empty.
- **from-url name injection**: `name='x"; DROP TABLE _datasets; --'` → 422; `/api/datasets` still 200.
- **from-url SSRF**: `url="http://127.0.0.1:8000/health"` → 400 with `detail` mentioning the URL isn't allowed; also `http://169.254.169.254/x.geojson` → 400. IP literals need no DNS or network.
- **DuckDB sandbox**: `app.app.state.db.conn.execute("SELECT * FROM read_text('/etc/passwd')")` raises `duckdb.PermissionException`. `SET enable_external_access = true` raises.
- **Error leakage**:
  - `POST /api/query/nearest` with dataset `nope` → 404 `"Dataset or column not found"`, with no `Catalog` in the body.
  - A filter on a missing column of `ingested_dataset` → 400 generic.
  - A corrupt `bad.geojson` upload → 400 whose `detail` does not contain `str(data_dir)`.
  - `app_no_raise` + monkeypatch `geo_app.routers.query.query_bbox` to raise `RuntimeError(f"boom {data_dir}")` → 500 `{"detail": "Internal server error"}`.
- **Read-only** (`readonly_app`):
  - upload → 403, from-url → 403 (even with a valid body), `DELETE /api/datasets/x` → 403.
  - `GET /api/datasets` 200, `GET /health` has `read_only: true`, `GET /api/builtins/available` 200.
  - Default `app` health has `read_only: false`.
- **Builtin idempotency**: monkeypatch `download_to_file` with a counter that writes the sample geojson; call `/api/builtins/load` twice → counter == 1.
- **Existing suite**: all 18 existing tests still pass unchanged (`test_upload_no_filename` accepts 400/422).

### Edge cases

- Names left on the live PVC from before this fix (invalid under the new pattern) are skipped by `reregister_views` rather than crashing startup.
- IPv4-mapped IPv6 and CGNAT ranges.
- A redirect chain from a public host to a private host.
- An empty filename (existing 400/422 behavior is kept).
- A relative `DATA_DIR` resolves to an absolute path, so the sandbox still matches.

---

## VALIDATION COMMANDS

### Level 1: Static Validation (REQUIRED)

```bash
ruff check src/ tests/
ruff format --check src/ tests/
```

(The project has no mypy or pyright; don't add one in this feature.)

### Level 2: Unit + Integration Tests

```bash
pytest tests/ -v
```

If a failure appears, check whether it's pre-existing with `git stash && pytest -q && git stash pop`. The baseline is 18 passed.

### Level 3: Container build

```bash
docker build -t duckdb-geo-demo:feat-001 . && docker run --rm duckdb-geo-demo:feat-001 env | grep READ_ONLY=true
```

(Skip if Docker isn't available in the devcontainer, and note that in the execution report.)

### Level 4: Manual Validation

```bash
export DATA_DIR=/tmp/geodata-feat001
READ_ONLY=true uvicorn geo_app.main:app --port 8765 &
curl -s localhost:8765/health                                    # read_only: true
curl -s -o /dev/null -w '%{http_code}\n' -F file=@README.md localhost:8765/api/ingest/upload   # 403
curl -s -o /dev/null -w '%{http_code}\n' -X DELETE localhost:8765/api/datasets/x                        # 403
kill %1
uvicorn geo_app.main:app --port 8765 &
curl -s -X POST localhost:8765/api/ingest/from-url -H 'content-type: application/json' \
  -d '{"url":"http://169.254.169.254/latest/meta-data/x.geojson"}'  # 400, URL not allowed
kill %1
```

In a browser at `READ_ONLY=true`: the upload section and the × delete buttons are hidden, and built-in datasets still load and render.

---

## ACCEPTANCE CRITERIA

- [ ] The client-supplied upload filename is never used in a filesystem path or SQL. Uploads are stored as `<uuid4hex><allowlisted-ext>` under `DATA_DIR/uploads/`.
- [ ] Every dataset name reaching SQL matches `^[a-z][a-z0-9_]{0,62}$`. Invalid user names get 422 or 400.
- [ ] All SQL path literals go through `quote_literal`.
- [ ] The DuckDB connection is sandboxed to `DATA_DIR`, and the configuration is locked.
- [ ] `from-url` only reaches public http(s) addresses, re-validates every redirect hop, and enforces `MAX_UPLOAD_MB`.
- [ ] No response body contains exception text from DuckDB, httpx or the filesystem. Unhandled errors → 500 `"Internal server error"`, logged server-side.
- [ ] With `READ_ONLY=true`: ingest and delete → 403, reads and built-in loads work, and the frontend hides write controls. The Docker image defaults to `READ_ONLY=true`.
- [ ] `ruff check` and `ruff format --check` are clean, and all tests pass (18 existing plus the new ones).
- [ ] README documents `READ_ONLY` and `MAX_UPLOAD_MB`.

## COMPLETION CHECKLIST

- [ ] All tasks completed in order, each task's validation passed
- [ ] Level 1–2 validation passed; Level 3–4 run or skip explicitly noted
- [ ] No regressions in existing tests
- [ ] Commit(s) use conventional prefixes (`fix(security): ...`, `feat: read-only mode`, `test: ...`)

---

## NOTES

- **Operational follow-ups (not code, for the operator):**
  - Set `READ_ONLY=true` in the K8s deployment manifest (outside this repo), or rely on the new image default.
  - After deploying, inspect the live `_datasets` table and `DATA_DIR/uploads/` for anything the public uploaded while the endpoints were open, and delete it.
  - Check whether anything was written outside `/data`: the root FS is read-only, but the PVC wasn't protected.
- **Out of scope, tracked in `.features/feature-list.md`:**
  - FEAT-002, frontend stored XSS via `innerHTML`/`setHTML`. Lower risk once production is read-only, but must be fixed before any writable public deploy.
  - FEAT-003, devcontainer "SPD" cleanup.
  - FEAT-004, secret scanning.
  - FEAT-005, API-key auth.
- **Design decisions:**
  - Read-only is a dependency rather than conditional router registration. It keeps the OpenAPI docs stable and is trivially testable.
  - Built-in loading stays enabled in read-only mode because the demo needs data. It's bounded to 4 fixed URLs and is idempotent.
  - DNS-rebinding is a residual risk in `safe_fetch`. It's accepted because the endpoint is disabled in production. Connect-time IP pinning would need a custom transport and isn't worth it for a demo.
- Shapefile upload is effectively broken for single `.shp` files (no sidecar files). That's a pre-existing issue and not addressed here.

**Confidence score for one-pass success: 8/10.** The main risks:
- `allowed_directories` path matching if any code path builds a non-resolved path. Mitigated by the `data_dir` validator.
- Starlette re-raise semantics in the 500-handler test. Handled via `raise_server_exceptions=False`.
