import re
from pathlib import Path
from typing import Any

from geo_app.config import Settings
from geo_app.db import DuckDBManager

LAT_NAMES = {"lat", "latitude", "y"}
LON_NAMES = {"lon", "longitude", "lng", "x"}


def detect_format(filename: str) -> str:
    suffix = Path(filename).suffix.lower()
    format_map = {
        ".geojson": "geojson",
        ".json": "geojson",
        ".shp": "shapefile",
        ".csv": "csv",
        ".parquet": "parquet",
        ".geoparquet": "parquet",
    }
    return format_map.get(suffix, "unknown")


def sanitize_name(name: str) -> str:
    name = Path(name).stem
    name = re.sub(r"[^a-zA-Z0-9_]", "_", name)
    name = re.sub(r"_+", "_", name).strip("_").lower()
    return name or "dataset"


def _find_lat_lon_columns(columns: list[str]) -> tuple[str, str] | None:
    lat_col = None
    lon_col = None
    for col in columns:
        if col.lower() in LAT_NAMES:
            lat_col = col
        if col.lower() in LON_NAMES:
            lon_col = col
    if lat_col and lon_col:
        return lat_col, lon_col
    return None


def ingest_file(
    db: DuckDBManager,
    settings: Settings,
    file_path: Path,
    original_filename: str,
    dataset_name: str | None = None,
) -> dict[str, Any]:
    fmt = detect_format(original_filename)
    name = dataset_name or sanitize_name(original_filename)
    parquet_path = settings.parquet_dir / f"{name}.parquet"

    with db.write_cursor() as cur:
        if fmt == "parquet":
            cur.execute(
                f"COPY (SELECT * FROM read_parquet('{file_path}')) "
                f"TO '{parquet_path}' (FORMAT PARQUET)"
            )
        elif fmt in ("geojson", "shapefile"):
            # ST_Read produces 'geom' column; rename to 'geometry' for consistency
            cur.execute(
                f"COPY (SELECT * EXCLUDE(geom), geom AS geometry FROM ST_Read('{file_path}')) "
                f"TO '{parquet_path}' (FORMAT PARQUET)"
            )
        elif fmt == "csv":
            # Read CSV and detect lat/lon columns
            cur.execute(f"CREATE OR REPLACE TEMP TABLE _csv_import AS SELECT * FROM '{file_path}'")
            cols_result = cur.execute(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name = '_csv_import'"
            ).fetchall()
            columns = [r[0] for r in cols_result]
            latlon = _find_lat_lon_columns(columns)
            if latlon:
                lat_col, lon_col = latlon
                cur.execute(
                    f'COPY (SELECT *, ST_Point("{lon_col}", "{lat_col}") AS geometry '
                    f"FROM _csv_import) TO '{parquet_path}' (FORMAT PARQUET)"
                )
            else:
                cur.execute(
                    f"COPY (SELECT * FROM _csv_import) TO '{parquet_path}' (FORMAT PARQUET)"
                )
            cur.execute("DROP TABLE IF EXISTS _csv_import")
        else:
            raise ValueError(f"Unsupported format: {fmt}")

        # Extract metadata
        metadata = _extract_metadata(cur, parquet_path)

        # Register view
        cur.execute(
            f"CREATE OR REPLACE VIEW \"{name}\" AS SELECT * FROM read_parquet('{parquet_path}')"
        )

        # Upsert metadata
        cur.execute(
            """
            INSERT OR REPLACE INTO _datasets
                (name, original_filename, format, geometry_type,
                 feature_count, bbox_minx, bbox_miny, bbox_maxx, bbox_maxy)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                name,
                original_filename,
                fmt,
                metadata.get("geometry_type"),
                metadata.get("feature_count"),
                metadata.get("bbox_minx"),
                metadata.get("bbox_miny"),
                metadata.get("bbox_maxx"),
                metadata.get("bbox_maxy"),
            ],
        )

    return {
        "status": "ok",
        "dataset_name": name,
        "feature_count": metadata.get("feature_count"),
        "geometry_type": metadata.get("geometry_type"),
    }


def _extract_metadata(cur: Any, parquet_path: Path) -> dict[str, Any]:
    metadata: dict[str, Any] = {}

    count = cur.execute(f"SELECT count(*) FROM read_parquet('{parquet_path}')").fetchone()[0]
    metadata["feature_count"] = count

    # Check if geometry column exists (could be 'geometry' or 'geom')
    cols = cur.execute(
        f"SELECT name FROM parquet_schema('{parquet_path}') WHERE name IN ('geometry', 'geom')"
    ).fetchall()
    geom_col = cols[0][0] if cols else None

    if geom_col:
        try:
            sql = (
                f'SELECT ST_GeometryType("{geom_col}") '
                f"FROM read_parquet('{parquet_path}') LIMIT 1"
            )
            geom_type = cur.execute(sql).fetchone()
            if geom_type:
                metadata["geometry_type"] = geom_type[0]

            bbox = cur.execute(
                f'SELECT MIN(ST_XMin("{geom_col}")), MIN(ST_YMin("{geom_col}")), '
                f'MAX(ST_XMax("{geom_col}")), MAX(ST_YMax("{geom_col}")) '
                f"FROM read_parquet('{parquet_path}')"
            ).fetchone()
            if bbox and bbox[0] is not None:
                metadata["bbox_minx"] = bbox[0]
                metadata["bbox_miny"] = bbox[1]
                metadata["bbox_maxx"] = bbox[2]
                metadata["bbox_maxy"] = bbox[3]
        except Exception:
            pass

    return metadata
