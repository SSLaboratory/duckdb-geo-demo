import threading
from collections.abc import Generator
from contextlib import contextmanager

import duckdb

from geo_app.config import Settings


class DuckDBManager:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._write_lock = threading.Lock()
        self._conn: duckdb.DuckDBPyConnection | None = None

    def initialize(self) -> None:
        self._conn = duckdb.connect(str(self._settings.duckdb_path))
        ext_dir = str(self._settings.extensions_dir)
        self._conn.execute(f"SET extension_directory = '{ext_dir}'")
        self._conn.execute("INSTALL spatial")
        self._conn.execute("LOAD spatial")
        self._init_metadata_table()

    def _init_metadata_table(self) -> None:
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS _datasets (
                name VARCHAR PRIMARY KEY,
                original_filename VARCHAR,
                format VARCHAR,
                geometry_type VARCHAR,
                feature_count BIGINT,
                bbox_minx DOUBLE,
                bbox_miny DOUBLE,
                bbox_maxx DOUBLE,
                bbox_maxy DOUBLE,
                created_at TIMESTAMP DEFAULT current_timestamp
            )
        """)

    def reregister_views(self) -> None:
        rows = self._conn.execute("SELECT name FROM _datasets").fetchall()
        parquet_dir = self._settings.parquet_dir
        for (name,) in rows:
            parquet_path = parquet_dir / f"{name}.parquet"
            if parquet_path.exists():
                self._conn.execute(
                    f'CREATE OR REPLACE VIEW "{name}" AS '
                    f"SELECT * FROM read_parquet('{parquet_path}')"
                )

    @contextmanager
    def read_cursor(self) -> Generator[duckdb.DuckDBPyConnection, None, None]:
        cursor = self._conn.cursor()
        try:
            yield cursor
        finally:
            cursor.close()

    @contextmanager
    def write_cursor(self) -> Generator[duckdb.DuckDBPyConnection, None, None]:
        with self._write_lock:
            cursor = self._conn.cursor()
            try:
                yield cursor
            finally:
                cursor.close()

    @property
    def conn(self) -> duckdb.DuckDBPyConnection:
        return self._conn

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None
