from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from geo_app.config import Settings
from geo_app.db import DuckDBManager


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


app = create_app()
