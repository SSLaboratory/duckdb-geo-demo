from typing import Any

from fastapi import APIRouter, Request

router = APIRouter()


@router.get("/health")
async def health(request: Request) -> dict[str, Any]:
    db = request.app.state.db
    with db.read_cursor() as cur:
        version = cur.execute("SELECT version()").fetchone()[0]
        spatial_loaded = bool(
            cur.execute(
                "SELECT * FROM duckdb_extensions() WHERE extension_name = 'spatial' AND loaded"
            ).fetchone()
        )
        dataset_count = cur.execute("SELECT count(*) FROM _datasets").fetchone()[0]

    return {
        "status": "ok",
        "duckdb_version": version,
        "spatial_loaded": spatial_loaded,
        "dataset_count": dataset_count,
        "read_only": request.app.state.settings.read_only,
    }
