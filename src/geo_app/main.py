import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import duckdb
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from geo_app.config import Settings
from geo_app.db import DuckDBManager

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    settings: Settings = app.state.settings
    db: DuckDBManager = app.state.db

    # Create directories
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    settings.parquet_dir.mkdir(parents=True, exist_ok=True)
    settings.extensions_dir.mkdir(parents=True, exist_ok=True)

    # Initialize DB and spatial extension
    db.initialize()
    db.reregister_views()

    yield

    db.close()


def create_app(settings: Settings | None = None) -> FastAPI:
    if settings is None:
        settings = Settings()

    app = FastAPI(title="DuckDB Geo Demo", version="0.1.0", lifespan=lifespan)
    app.state.settings = settings
    app.state.db = DuckDBManager(settings)
    _register_exception_handlers(app)

    # Register routers
    from geo_app.routers import builtins, datasets, health, ingest, query

    app.include_router(health.router)
    app.include_router(datasets.router)
    app.include_router(ingest.router)
    app.include_router(query.router)
    app.include_router(builtins.router)

    # Mount static files
    from pathlib import Path

    static_dir = Path(__file__).parent / "static"
    if static_dir.exists():
        app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="static")

    return app


def _register_exception_handlers(app: FastAPI) -> None:
    # Structured, generic error bodies: DuckDB and Python exception text can
    # include server paths and SQL, so it is logged server-side only.

    @app.exception_handler(duckdb.CatalogException)
    async def _catalog_error(request: Request, exc: duckdb.CatalogException) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": "Dataset or column not found"})

    @app.exception_handler(duckdb.BinderException)
    async def _binder_error(request: Request, exc: duckdb.BinderException) -> JSONResponse:
        return JSONResponse(status_code=400, content={"detail": "Invalid query for this dataset"})

    @app.exception_handler(duckdb.Error)
    async def _duckdb_error(request: Request, exc: duckdb.Error) -> JSONResponse:
        logger.exception("Database error on %s %s", request.method, request.url.path)
        return JSONResponse(status_code=500, content={"detail": "Internal server error"})

    @app.exception_handler(Exception)
    async def _unhandled_error(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled error on %s %s", request.method, request.url.path)
        return JSONResponse(status_code=500, content={"detail": "Internal server error"})


app = create_app()
