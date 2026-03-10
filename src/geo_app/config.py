from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    data_dir: Path = Path("/data")

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
