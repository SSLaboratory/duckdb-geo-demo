# DuckDB Geo Demo

A FastAPI + DuckDB spatial application for GeoParquet data pipelines.

## Project Structure

- `src/geo_app/` — Python package (src layout)
- `src/geo_app/main.py` — FastAPI app factory with lifespan
- `src/geo_app/config.py` — pydantic-settings configuration
- `src/geo_app/db.py` — DuckDB connection manager (singleton + write lock)
- `src/geo_app/routers/` — API route handlers
- `src/geo_app/services/` — Business logic (ingestion, queries, built-in datasets)
- `src/geo_app/models/` — Pydantic schemas
- `src/geo_app/static/` — Frontend (MapLibre GL + vanilla JS)
- `tests/` — pytest test suite

## Development

```bash
pip install -e ".[dev]"
DATA_DIR=/tmp/geodata uvicorn geo_app.main:app --reload
pytest tests/ -v
```

## Conventions

- **Python**: 3.11, type hints on all function signatures
- **Formatting/Linting**: ruff (format + lint), configured in pyproject.toml
- **Dependencies**: pyproject.toml (no requirements.txt)
- **Config**: pydantic-settings, all config via environment variables
- **DuckDB**: Single connection, threading write lock for mutations, read cursors for queries
- **Storage**: All writable state under DATA_DIR (default `/data`), never system temp dirs
- **API style**: RESTful, JSON responses, GeoJSON for spatial data
- **Error handling**: FastAPI exception handlers, structured error responses
- **Testing**: pytest with tmp_path fixtures, no external dependencies, no network calls in tests
- **Frontend**: No build step, no bundler — static HTML/JS/CSS served by FastAPI
- **Security**: No raw SQL from user input — use parameterized queries or structured filter params
- **Commits**: Conventional commits (feat:, fix:, chore:, etc.)

## Key Technical Details

- DuckDB spatial extension must be installed to `/data/.duckdb_extensions` (read-only root FS in production)
- Views must be re-registered on startup from `_datasets` metadata table
- GeoJSON export endpoints default to 1000 feature limit
- File uploads saved to `DATA_DIR/uploads/`, GeoParquet stored in `DATA_DIR/parquet/`

## Deployment

- Container image: `ghcr.io/sslaboratory/duckdb-geo-demo:latest`
- K8s: port 8000, PVC at `/data`, read-only root FS, non-root (UID 1000)
- Base image: `python:3.11-slim` (DuckDB needs glibc)
