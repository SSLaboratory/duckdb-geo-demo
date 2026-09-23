import ipaddress
import json
from collections.abc import Callable
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from geo_app.config import Settings
from geo_app.main import create_app


@pytest.fixture()
def data_dir(tmp_path: Path) -> Path:
    return tmp_path / "data"


@pytest.fixture()
def settings(data_dir: Path) -> Settings:
    return Settings(data_dir=data_dir)


@pytest.fixture()
def app(settings: Settings) -> TestClient:
    application = create_app(settings)
    with TestClient(application) as client:
        yield client


@pytest.fixture()
def sample_geojson(tmp_path: Path) -> Path:
    geojson = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [0.0, 0.0]},
                "properties": {"name": "Origin", "value": 1},
            },
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [1.0, 1.0]},
                "properties": {"name": "One-One", "value": 2},
            },
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [10.0, 10.0]},
                "properties": {"name": "Ten-Ten", "value": 3},
            },
        ],
    }
    path = tmp_path / "sample.geojson"
    path.write_text(json.dumps(geojson))
    return path


@pytest.fixture()
def sample_csv(tmp_path: Path) -> Path:
    csv_content = "name,latitude,longitude,value\nA,0.0,0.0,1\nB,1.0,1.0,2\nC,10.0,10.0,3\n"
    path = tmp_path / "sample.csv"
    path.write_text(csv_content)
    return path


@pytest.fixture()
def ingested_dataset(app: TestClient, sample_geojson: Path) -> str:
    """Upload a sample GeoJSON and return the dataset name."""
    with open(sample_geojson, "rb") as f:
        resp = app.post("/api/ingest/upload", files={"file": ("sample.geojson", f)})
    assert resp.status_code == 200
    return resp.json()["dataset_name"]


@pytest.fixture()
def readonly_app(data_dir: Path) -> TestClient:
    application = create_app(Settings(data_dir=data_dir, read_only=True))
    with TestClient(application) as client:
        yield client


@pytest.fixture()
def app_no_raise(settings: Settings) -> TestClient:
    """Client that returns 500 responses instead of re-raising server exceptions."""
    application = create_app(settings)
    with TestClient(application, raise_server_exceptions=False) as client:
        yield client


@pytest.fixture()
def fake_dns(monkeypatch: pytest.MonkeyPatch) -> Callable[..., None]:
    """Replace DNS resolution in safe_fetch so tests never touch the network."""

    def set_addresses(*addresses: str) -> None:
        async def _resolve(host: str, port: int) -> list[str]:
            try:
                return [str(ipaddress.ip_address(host))]  # IP literals resolve to themselves
            except ValueError:
                return list(addresses)

        monkeypatch.setattr("geo_app.services.safe_fetch._resolve", _resolve)

    return set_addresses
