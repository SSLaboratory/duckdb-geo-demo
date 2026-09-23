from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    data_dir: Path = Path("/data")
    read_only: bool = False
    max_upload_mb: int = Field(default=100, gt=0)

    @field_validator("data_dir")
    @classmethod
    def _resolve_data_dir(cls, v: Path) -> Path:
        # Absolute paths keep DuckDB's allowed_directories sandbox matching
        return Path(v).resolve()

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024

    @property
    def duckdb_path(self) -> Path:
        return self.data_dir / "geo.duckdb"

    @property
    def upload_dir(self) -> Path:
        return self.data_dir / "uploads"

    @property
    def parquet_dir(self) -> Path:
        return self.data_dir / "parquet"

    @property
    def extensions_dir(self) -> Path:
        return self.data_dir / ".duckdb_extensions"

    model_config = {"env_prefix": ""}


settings = Settings()
