import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request

from geo_app.dependencies import require_writable
from geo_app.models.schemas import DatasetInfo, DatasetList
from geo_app.naming import is_valid_dataset_name

router = APIRouter(prefix="/api/datasets", tags=["datasets"])


@router.get("", response_model=DatasetList)
async def list_datasets(request: Request) -> DatasetList:
    db = request.app.state.db
    with db.read_cursor() as cur:
        rows = cur.execute(
            "SELECT name, original_filename, format, geometry_type, "
            "feature_count, bbox_minx, bbox_miny, bbox_maxx, bbox_maxy, created_at "
            "FROM _datasets ORDER BY created_at DESC"
        ).fetchall()

    datasets = []
    for row in rows:
        bbox = None
        if row[5] is not None:
            bbox = [row[5], row[6], row[7], row[8]]
        datasets.append(
            DatasetInfo(
                name=row[0],
                original_filename=row[1],
                format=row[2],
                geometry_type=row[3],
                feature_count=row[4],
                bbox=bbox,
                created_at=row[9],
            )
        )
    return DatasetList(datasets=datasets, count=len(datasets))


@router.get("/{name}")
async def get_dataset(request: Request, name: str) -> DatasetInfo:
    db = request.app.state.db
    with db.read_cursor() as cur:
        row = cur.execute(
            "SELECT name, original_filename, format, geometry_type, "
            "feature_count, bbox_minx, bbox_miny, bbox_maxx, bbox_maxy, created_at "
            "FROM _datasets WHERE name = ?",
            [name],
        ).fetchone()

    if not row:
        raise HTTPException(status_code=404, detail=f"Dataset '{name}' not found")

    bbox = None
    if row[5] is not None:
        bbox = [row[5], row[6], row[7], row[8]]
    return DatasetInfo(
        name=row[0],
        original_filename=row[1],
        format=row[2],
        geometry_type=row[3],
        feature_count=row[4],
        bbox=bbox,
        created_at=row[9],
    )


@router.get("/{name}/geojson")
async def get_dataset_geojson(
    request: Request,
    name: str,
    limit: int = 1000,
    minx: float | None = None,
    miny: float | None = None,
    maxx: float | None = None,
    maxy: float | None = None,
) -> dict[str, Any]:
    db = request.app.state.db

    if not is_valid_dataset_name(name):
        raise HTTPException(status_code=400, detail="Invalid dataset name")

    # Verify dataset exists
    with db.read_cursor() as cur:
        exists = cur.execute("SELECT 1 FROM _datasets WHERE name = ?", [name]).fetchone()
        if not exists:
            raise HTTPException(status_code=404, detail=f"Dataset '{name}' not found")

        base = (
            f'SELECT * EXCLUDE(geometry), ST_AsGeoJSON(geometry) AS geojson_geometry FROM "{name}"'
        )

        params: list[Any] = []
        if minx is not None and miny is not None and maxx is not None and maxy is not None:
            base += " WHERE ST_Intersects(geometry, ST_MakeEnvelope(?, ?, ?, ?))"
            params.extend([minx, miny, maxx, maxy])

        base += " LIMIT ?"
        params.append(min(limit, 10000))

        result = cur.execute(base, params)
        columns = [desc[0] for desc in result.description]
        rows = result.fetchall()

    # Build GeoJSON
    geom_idx = columns.index("geojson_geometry")
    features = []
    for row in rows:
        properties = {}
        geometry = None
        for i, col in enumerate(columns):
            if i == geom_idx:
                try:
                    geometry = json.loads(row[i]) if isinstance(row[i], str) else row[i]
                except (json.JSONDecodeError, TypeError):
                    geometry = None
            elif col.lower() != "geometry":
                val = row[i]
                if hasattr(val, "isoformat"):
                    val = val.isoformat()
                properties[col] = val
        features.append(
            {
                "type": "Feature",
                "geometry": geometry,
                "properties": properties,
            }
        )

    return {"type": "FeatureCollection", "features": features}


@router.delete("/{name}", dependencies=[Depends(require_writable)])
async def delete_dataset(request: Request, name: str) -> dict[str, str]:
    db = request.app.state.db
    settings = request.app.state.settings

    if not is_valid_dataset_name(name):
        raise HTTPException(status_code=400, detail="Invalid dataset name")

    with db.write_cursor() as cur:
        exists = cur.execute("SELECT 1 FROM _datasets WHERE name = ?", [name]).fetchone()
        if not exists:
            raise HTTPException(status_code=404, detail=f"Dataset '{name}' not found")

        cur.execute(f'DROP VIEW IF EXISTS "{name}"')
        cur.execute("DELETE FROM _datasets WHERE name = ?", [name])

    # Remove parquet file
    parquet_path = settings.parquet_dir / f"{name}.parquet"
    if parquet_path.exists():
        parquet_path.unlink()

    return {"status": "deleted", "dataset": name}
