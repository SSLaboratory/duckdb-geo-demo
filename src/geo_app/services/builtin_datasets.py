from typing import Any

from geo_app.config import Settings
from geo_app.db import DuckDBManager
from geo_app.models.schemas import BuiltinDataset
from geo_app.services.ingestion import ingest_file
from geo_app.services.safe_fetch import download_to_file

_NE_BASE = "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson"

BUILTIN_CATALOG: list[BuiltinDataset] = [
    BuiltinDataset(
        id="ne-countries-110m",
        name="Natural Earth Countries (110m)",
        description="Country boundaries at 1:110m scale",
        url=f"{_NE_BASE}/ne_110m_admin_0_countries.geojson",
        format="geojson",
    ),
    BuiltinDataset(
        id="ne-populated-places-110m",
        name="Natural Earth Populated Places (110m)",
        description="Major populated places at 1:110m scale",
        url=f"{_NE_BASE}/ne_110m_populated_places_simple.geojson",
        format="geojson",
    ),
    BuiltinDataset(
        id="ne-rivers-110m",
        name="Natural Earth Rivers (110m)",
        description="Major rivers and lake centerlines at 1:110m scale",
        url=f"{_NE_BASE}/ne_110m_rivers_lake_centerlines.geojson",
        format="geojson",
    ),
    BuiltinDataset(
        id="ne-lakes-110m",
        name="Natural Earth Lakes (110m)",
        description="Major lakes at 1:110m scale",
        url=f"{_NE_BASE}/ne_110m_lakes.geojson",
        format="geojson",
    ),
]


def get_available() -> list[BuiltinDataset]:
    return BUILTIN_CATALOG


def find_builtin(dataset_id: str) -> BuiltinDataset | None:
    for ds in BUILTIN_CATALOG:
        if ds.id == dataset_id:
            return ds
    return None


async def load_builtin(
    db: DuckDBManager,
    settings: Settings,
    dataset_id: str,
) -> dict[str, Any]:
    builtin = find_builtin(dataset_id)
    if not builtin:
        raise ValueError(f"Unknown built-in dataset: {dataset_id}")

    dataset_name = builtin.id.replace("-", "_")

    # Idempotent: repeated loads (e.g. public clicks) never re-download
    existing = _existing_dataset(db, settings, dataset_name)
    if existing:
        return existing

    # Download to upload dir
    download_path = settings.upload_dir / f"{builtin.id}.{builtin.format}"
    await download_to_file(builtin.url, download_path, settings.max_upload_bytes)

    # Ingest using standard pipeline
    result = ingest_file(
        db=db,
        settings=settings,
        file_path=download_path,
        original_filename=f"{builtin.id}.{builtin.format}",
        dataset_name=dataset_name,
    )

    return result


def _existing_dataset(
    db: DuckDBManager, settings: Settings, dataset_name: str
) -> dict[str, Any] | None:
    if not (settings.parquet_dir / f"{dataset_name}.parquet").exists():
        return None
    with db.read_cursor() as cur:
        row = cur.execute(
            "SELECT feature_count, geometry_type FROM _datasets WHERE name = ?",
            [dataset_name],
        ).fetchone()
    if not row:
        return None
    return {
        "status": "ok",
        "dataset_name": dataset_name,
        "feature_count": row[0],
        "geometry_type": row[1],
    }
