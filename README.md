# DuckDB Geo Demo

A full-stack geospatial application built with FastAPI and DuckDB's spatial extension. Upload, query, and visualize geospatial data through a REST API and interactive MapLibre GL web interface — all backed by GeoParquet storage.

## Features

- **Multi-format ingestion** — Upload GeoJSON, Shapefile, CSV (with auto lat/lon detection), or GeoParquet files
- **Spatial queries** — Bounding box intersection, K-nearest neighbor, spatial joins, and attribute filtering
- **Built-in datasets** — One-click loading of Natural Earth data (countries, populated places, rivers, lakes)
- **GeoParquet storage** — All data converted to columnar GeoParquet for efficient querying
- **Interactive map UI** — MapLibre GL frontend with dataset management, feature popups, and layer toggling
- **Production-ready** — Non-root container, read-only root FS support, health checks, CI/CD to GHCR

## Quick Start

### Local Development

```bash
# Install dependencies
pip install -e ".[dev]"

# Start the dev server (data stored in /tmp/geodata)
DATA_DIR=/tmp/geodata uvicorn geo_app.main:app --reload

# Open http://localhost:8000 in your browser
```

### Docker

```bash
# Build
docker build -t duckdb-geo-demo .

# Run read-only (the image default; persistent data in /tmp/data)
docker run --rm -p 8000:8000 -v /tmp/data:/data duckdb-geo-demo

# Run with uploads and deletes enabled
docker run --rm -p 8000:8000 -e READ_ONLY=false -v /tmp/data:/data duckdb-geo-demo
```

### Kubernetes

The container image is published to GHCR on every push to `main`:

```
ghcr.io/sslaboratory/duckdb-geo-demo:latest
```

K8s deployment requirements:
- **Port**: 8000
- **PVC**: mounted at `/data` (5Gi) — stores DuckDB database, GeoParquet files, uploads, and extensions
- **Read-only root FS**: all writable state goes to `/data`
- **Non-root**: runs as UID 1000
- **Health check**: `GET /health`

## Startup Procedure

1. **Directory creation** — the app creates `uploads/`, `parquet/`, and `.duckdb_extensions/` subdirectories under `DATA_DIR`
2. **DuckDB initialization** — opens (or creates) `DATA_DIR/geo.duckdb`, installs and loads the spatial extension to `DATA_DIR/.duckdb_extensions/`
3. **Metadata table** — creates the `_datasets` table if it doesn't exist (tracks all ingested datasets)
4. **Sandbox** — restricts DuckDB file access to `DATA_DIR` (`allowed_directories` + `enable_external_access = false`) and locks the configuration
5. **View re-registration** — iterates `_datasets` and recreates DuckDB views pointing to existing parquet files (views are lost on restart since they live in-memory)
6. **Static files** — mounts the frontend at `/`
7. **Ready** — Uvicorn starts accepting requests on port 8000

## Shutdown Procedure

1. **Uvicorn** receives SIGTERM (or Ctrl+C in dev mode)
2. **Lifespan cleanup** closes the DuckDB connection gracefully
3. All state is persisted in `DATA_DIR` — the database and parquet files survive restarts

## API Reference

### Health

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Status, DuckDB version, spatial extension check, dataset count |

### Datasets

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/datasets` | List all datasets with metadata |
| `GET` | `/api/datasets/{name}` | Get dataset details |
| `GET` | `/api/datasets/{name}/geojson` | Export as GeoJSON (supports `limit`, `minx/miny/maxx/maxy` bbox params) |
| `DELETE` | `/api/datasets/{name}` | Delete dataset (removes view, metadata, and parquet file; `403` when `READ_ONLY=true`) |

### Ingestion

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/ingest/upload` | Upload a file (multipart form, field: `file`) |
| `POST` | `/api/ingest/from-url` | Ingest from URL (`{"url": "...", "name": "..."}`) |

Supported formats: `.geojson`, `.json`, `.shp`, `.csv`, `.parquet`

Both endpoints return `403` when `READ_ONLY=true`. Uploads and downloads are capped at `MAX_UPLOAD_MB` (`413` when exceeded). Uploaded files are stored under a server-generated name. `from-url` only fetches public `http`/`https` addresses (private, loopback, link-local and metadata addresses are rejected, including via redirects). The optional `name` must match `^[a-z][a-z0-9_]{0,62}$`.

CSV files are auto-scanned for lat/lon columns (`lat`/`latitude`/`y` and `lon`/`longitude`/`lng`/`x`, case-insensitive).

### Spatial Queries

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/query/bbox` | Bounding box query (`dataset`, `minx`, `miny`, `maxx`, `maxy`, `limit`) |
| `POST` | `/api/query/nearest` | K-nearest neighbor (`{"dataset", "lon", "lat", "k"}`) |
| `POST` | `/api/query/spatial-join` | Spatial join (`{"left_dataset", "right_dataset", "predicate", "limit"}`) |
| `POST` | `/api/query/filter` | Attribute filter (`{"dataset", "filters": [{"column", "op", "value"}], "limit"}`) |

Filter operators: `eq`, `ne`, `gt`, `lt`, `gte`, `lte`, `like`

### Built-in Datasets

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/builtins/available` | List available built-in datasets |
| `POST` | `/api/builtins/load` | Download and ingest (`{"dataset": "ne-countries-110m"}`); no-op if already loaded. Available in read-only mode. |

Available: `ne-countries-110m`, `ne-populated-places-110m`, `ne-rivers-110m`, `ne-lakes-110m`

## Configuration

All configuration is via environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `DATA_DIR` | `/data` | Root directory for all persistent state |
| `READ_ONLY` | `false` (container image: `true`) | Disables upload, URL ingest and dataset deletion (`403`). Querying and built-in datasets still work. |
| `MAX_UPLOAD_MB` | `100` | Maximum size of an uploaded or downloaded file |

Derived paths (not configurable separately):
- `DATA_DIR/geo.duckdb` — DuckDB database
- `DATA_DIR/uploads/` — uploaded files
- `DATA_DIR/parquet/` — converted GeoParquet files
- `DATA_DIR/.duckdb_extensions/` — DuckDB spatial extension

## Project Structure

```
src/geo_app/
├── main.py              # App factory + lifespan
├── config.py            # pydantic-settings
├── db.py                # DuckDB manager (singleton + write lock)
├── routers/
│   ├── health.py        # GET /health
│   ├── datasets.py      # Dataset CRUD + GeoJSON export
│   ├── ingest.py        # File upload + URL ingest
│   ├── query.py         # Spatial query endpoints
│   └── builtins.py      # Built-in dataset loader
├── services/
│   ├── ingestion.py     # Format detection, conversion, metadata extraction
│   ├── spatial_query.py # Query builders (bbox, KNN, join, filter)
│   └── builtin_datasets.py  # Natural Earth catalog + download
├── models/
│   └── schemas.py       # Pydantic request/response models
└── static/
    ├── index.html       # MapLibre GL viewer
    ├── app.js           # Frontend logic
    └── style.css        # Dark theme styles
```

## Development

```bash
# Install with dev dependencies
pip install -e ".[dev]"

# Run tests
pytest tests/ -v

# Lint and format
ruff check src/ tests/
ruff format src/ tests/

# Or use make targets
make test
make lint
make dev
```

## CI/CD

Two GitHub Actions workflows run on push to `main`:

- **CI** (`.github/workflows/ci.yml`) — lint, format check, tests
- **Release** (`.github/workflows/release.yml`) — tests, then builds and pushes to `ghcr.io/sslaboratory/duckdb-geo-demo`

Image tags: `latest`, `main`, `<commit-sha>`, and semver (`v1.0.0` → `1.0.0`, `1.0`) when pushing version tags.
