from typing import Any

from geo_app.db import DuckDBManager
from geo_app.models.schemas import AttributeFilter

ALLOWED_OPS = {
    "eq": "=",
    "ne": "!=",
    "gt": ">",
    "lt": "<",
    "gte": ">=",
    "lte": "<=",
    "like": "LIKE",
}


def _validate_identifier(name: str) -> str:
    """Validate that a name is a safe SQL identifier."""
    if not name.replace("_", "").replace("-", "").isalnum():
        raise ValueError(f"Invalid identifier: {name}")
    return name


def _to_geojson_fc(rows: list[Any], columns: list[str]) -> dict[str, Any]:
    """Convert query results to a GeoJSON FeatureCollection."""
    geom_idx = None
    for i, col in enumerate(columns):
        if col.lower() == "geojson_geometry":
            geom_idx = i
            break

    features = []
    for row in rows:
        properties = {}
        geometry = None
        for i, col in enumerate(columns):
            if i == geom_idx:
                import json

                try:
                    geometry = json.loads(row[i]) if isinstance(row[i], str) else row[i]
                except (json.JSONDecodeError, TypeError):
                    geometry = None
            elif col.lower() != "geometry":
                val = row[i]
                # Convert non-JSON-serializable types
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


def _build_select_with_geojson(dataset: str) -> str:
    """Build a SELECT that excludes raw geometry and includes GeoJSON."""
    return (
        f"SELECT * EXCLUDE(geometry), ST_AsGeoJSON(geometry) AS geojson_geometry "
        f'FROM "{_validate_identifier(dataset)}"'
    )


def query_bbox(
    db: DuckDBManager,
    dataset: str,
    minx: float,
    miny: float,
    maxx: float,
    maxy: float,
    limit: int = 1000,
) -> dict[str, Any]:
    _validate_identifier(dataset)
    sql = (
        f"{_build_select_with_geojson(dataset)} "
        f"WHERE ST_Intersects(geometry, ST_MakeEnvelope(?, ?, ?, ?)) "
        f"LIMIT ?"
    )
    with db.read_cursor() as cur:
        result = cur.execute(sql, [minx, miny, maxx, maxy, limit])
        columns = [desc[0] for desc in result.description]
        rows = result.fetchall()
    return _to_geojson_fc(rows, columns)


def query_nearest(
    db: DuckDBManager,
    dataset: str,
    lon: float,
    lat: float,
    k: int = 5,
) -> dict[str, Any]:
    _validate_identifier(dataset)
    sql = (
        f"{_build_select_with_geojson(dataset)} "
        f"ORDER BY ST_Distance(geometry, ST_Point(?, ?)) "
        f"LIMIT ?"
    )
    with db.read_cursor() as cur:
        result = cur.execute(sql, [lon, lat, k])
        columns = [desc[0] for desc in result.description]
        rows = result.fetchall()
    return _to_geojson_fc(rows, columns)


def query_spatial_join(
    db: DuckDBManager,
    left_dataset: str,
    right_dataset: str,
    predicate: str = "st_intersects",
    limit: int = 1000,
) -> dict[str, Any]:
    _validate_identifier(left_dataset)
    _validate_identifier(right_dataset)

    allowed_predicates = {"st_intersects", "st_contains", "st_within", "st_overlaps", "st_touches"}
    if predicate.lower() not in allowed_predicates:
        raise ValueError(f"Invalid predicate: {predicate}. Allowed: {allowed_predicates}")

    sql = (
        f"SELECT a.* EXCLUDE(geometry), ST_AsGeoJSON(a.geometry) AS geojson_geometry "
        f'FROM "{left_dataset}" a JOIN "{right_dataset}" b '
        f"ON {predicate}(a.geometry, b.geometry) "
        f"LIMIT ?"
    )
    with db.read_cursor() as cur:
        result = cur.execute(sql, [limit])
        columns = [desc[0] for desc in result.description]
        rows = result.fetchall()
    return _to_geojson_fc(rows, columns)


def query_filter(
    db: DuckDBManager,
    dataset: str,
    filters: list[AttributeFilter],
    limit: int = 1000,
) -> dict[str, Any]:
    _validate_identifier(dataset)

    conditions = []
    params: list[Any] = []

    for f in filters:
        if f.op not in ALLOWED_OPS:
            raise ValueError(f"Invalid operator: {f.op}. Allowed: {list(ALLOWED_OPS.keys())}")
        col = _validate_identifier(f.column)
        sql_op = ALLOWED_OPS[f.op]
        conditions.append(f'"{col}" {sql_op} ?')
        params.append(f.value)

    where = " AND ".join(conditions) if conditions else "TRUE"
    params.append(limit)

    sql = f"{_build_select_with_geojson(dataset)} WHERE {where} LIMIT ?"
    with db.read_cursor() as cur:
        result = cur.execute(sql, params)
        columns = [desc[0] for desc in result.description]
        rows = result.fetchall()
    return _to_geojson_fc(rows, columns)
