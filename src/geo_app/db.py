import logging
import threading
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path

import duckdb

from geo_app.config import Settings
from geo_app.naming import is_valid_dataset_name

logger = logging.getLogger(__name__)


def quote_literal(value: str | Path) -> str:
    """Render a value as a single-quoted SQL string literal."""
    return "'" + str(value).replace("'", "''") + "'"


class DuckDBManager:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._write_lock = threading.Lock()
        self._conn: duckdb.DuckDBPyConnection | None = None

    def initialize(self) -> None:
        self._conn = duckdb.connect(str(self._settings.duckdb_path))
        ext_dir = self._settings.extensions_dir
        self._conn.execute(f"SET extension_directory = {quote_literal(ext_dir)}")
        self._conn.execute("INSTALL spatial")
        self._conn.execute("LOAD spatial")
        self._init_metadata_table()
        self._apply_sandbox()

    def _apply_sandbox(self) -> None:
        # Must run after LOAD spatial: disabling external access blocks extension loading
        allowed = str(self._settings.data_dir).rstrip("/") + "/"
        self._conn.execute("SET allowed_directories = ?", [[allowed]])
        self._conn.execute("SET enable_external_access = false")
        self._conn.execute("SET lock_configuration = true")

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
            if not is_valid_dataset_name(name):
                logger.warning("Skipping dataset with invalid name: %r", name)
                continue
            parquet_path = parquet_dir / f"{name}.parquet"
            if parquet_path.exists():
                self._conn.execute(
                    f'CREATE OR REPLACE VIEW "{name}" AS '
                    f"SELECT * FROM read_parquet({quote_literal(parquet_path)})"
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
