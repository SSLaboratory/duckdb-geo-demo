from typing import Any

import httpx

from geo_app.config import Settings
from geo_app.db import DuckDBManager
from geo_app.models.schemas import BuiltinDataset
from geo_app.services.ingestion import ingest_file

_NE_BASE = (
    "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson"
)

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

    # Download to upload dir
    download_path = settings.upload_dir / f"{builtin.id}.{builtin.format}"

    headers = {"User-Agent": "duckdb-geo-demo/0.1.0"}
    async with httpx.AsyncClient(timeout=120.0, headers=headers) as client:
        resp = await client.get(builtin.url, follow_redirects=True)
        resp.raise_for_status()
        download_path.write_bytes(resp.content)

    # Ingest using standard pipeline
    result = ingest_file(
        db=db,
        settings=settings,
        file_path=download_path,
        original_filename=f"{builtin.id}.{builtin.format}",
        dataset_name=builtin.id.replace("-", "_"),
    )

    return result
