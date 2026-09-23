"""Regression tests for FEAT-001 security hardening."""

import asyncio
import json
from pathlib import Path

import duckdb
import httpx
import pytest

from geo_app.config import Settings
from geo_app.db import quote_literal
from geo_app.main import create_app
from geo_app.naming import is_valid_dataset_name, sanitize_name, validate_dataset_name
from geo_app.services import safe_fetch
from geo_app.services.safe_fetch import (
    DownloadError,
    DownloadTooLargeError,
    UnsafeURLError,
    download_to_file,
    validate_public_url,
)

PUBLIC_IP = "93.184.216.34"


def _upload(client, filename: str, content: bytes):
    return client.post("/api/ingest/upload", files={"file": (filename, content)})


# --- naming ---------------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("2024.csv", "ds_2024"),
        ("a'b.geojson", "a_b"),
        ("../../x.geojson", "x"),
        ("'", "dataset"),
        ("Mixed-Case Name.csv", "mixed_case_name"),
    ],
)
def test_sanitize_name(raw: str, expected: str) -> None:
    assert sanitize_name(raw) == expected


def test_sanitize_name_is_always_valid() -> None:
    long_name = "a" * 200 + ".csv"
    assert len(sanitize_name(long_name)) <= 63
    for raw in ["2024.csv", "'", "_x_.csv", long_name, "ümlaut.geojson"]:
        assert is_valid_dataset_name(sanitize_name(raw))


@pytest.mark.parametrize("bad", ["_datasets", "A", 'x"y', "", "a-b", "1abc", "é"])
def test_validate_dataset_name_rejects(bad: str) -> None:
    with pytest.raises(ValueError):
        validate_dataset_name(bad)


def test_quote_literal_escapes_single_quotes() -> None:
    assert quote_literal("a'b") == "'a''b'"


# --- SSRF: URL validation -------------------------------------------------


@pytest.mark.parametrize(
    "url",
    [
        "file:///etc/passwd",
        "ftp://example.com/x.geojson",
        "http:///nohost",
        "http://127.0.0.1/",
        "http://10.0.0.5/internal",
        "http://169.254.169.254/latest/meta-data",
        "http://[::1]/",
        "http://[::ffff:127.0.0.1]/",
        "http://100.64.0.1/",
        "http://0.0.0.0/",
    ],
)
def test_validate_public_url_rejects(url: str) -> None:
    with pytest.raises(UnsafeURLError):
        asyncio.run(validate_public_url(url))


def test_validate_public_url_rejects_private_dns(fake_dns) -> None:
    fake_dns("192.168.1.5")
    with pytest.raises(UnsafeURLError):
        asyncio.run(validate_public_url("http://internal.example/x.geojson"))


def test_validate_public_url_rejects_mixed_dns(fake_dns) -> None:
    fake_dns(PUBLIC_IP, "10.0.0.1")
    with pytest.raises(UnsafeURLError):
        asyncio.run(validate_public_url("http://mixed.example/x.geojson"))


def test_validate_public_url_accepts_public(fake_dns) -> None:
    fake_dns(PUBLIC_IP)
    asyncio.run(validate_public_url("https://data.example/x.geojson"))


# --- SSRF: downloads ------------------------------------------------------


def _download(url: str, dest: Path, handler, max_bytes: int = 1024) -> None:
    transport = httpx.MockTransport(handler)
    asyncio.run(download_to_file(url, dest, max_bytes, transport=transport))


def test_download_writes_file(fake_dns, tmp_path: Path) -> None:
    fake_dns(PUBLIC_IP)
    dest = tmp_path / "out.geojson"
    _download("http://data.example/a.geojson", dest, lambda r: httpx.Response(200, content=b"ok"))
    assert dest.read_bytes() == b"ok"


def test_download_blocks_redirect_to_private(fake_dns, tmp_path: Path) -> None:
    fake_dns(PUBLIC_IP)
    requested: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested.append(str(request.url))
        return httpx.Response(302, headers={"location": "http://127.0.0.1:8000/health"})

    dest = tmp_path / "out.geojson"
    with pytest.raises(UnsafeURLError):
        _download("http://data.example/a.geojson", dest, handler)
    assert requested == ["http://data.example/a.geojson"]
    assert not dest.exists()


def test_download_too_many_redirects(fake_dns, tmp_path: Path) -> None:
    fake_dns(PUBLIC_IP)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(302, headers={"location": "/again"})

    with pytest.raises(DownloadError):
        _download("http://data.example/a.geojson", tmp_path / "out", handler)


def test_download_size_cap_streaming(fake_dns, tmp_path: Path) -> None:
    fake_dns(PUBLIC_IP)

    async def chunks():
        yield b"x" * 800
        yield b"x" * 800

    def handler(request: httpx.Request) -> httpx.Response:
        # Streamed body with no Content-Length header
        return httpx.Response(200, content=chunks())

    dest = tmp_path / "out"
    with pytest.raises(DownloadTooLargeError):
        _download("http://data.example/a.geojson", dest, handler, max_bytes=1024)
    assert not dest.exists()


def test_download_size_cap_content_length(fake_dns, tmp_path: Path) -> None:
    fake_dns(PUBLIC_IP)
    dest = tmp_path / "out"
    with pytest.raises(DownloadTooLargeError):
        _download(
            "http://data.example/a.geojson",
            dest,
            lambda r: httpx.Response(200, content=b"x" * 2048),
            max_bytes=1024,
        )
    assert not dest.exists()


def test_download_http_error_is_generic(fake_dns, tmp_path: Path) -> None:
    fake_dns(PUBLIC_IP)
    with pytest.raises(DownloadError) as exc_info:
        _download(
            "http://data.example/a.geojson",
            tmp_path / "out",
            lambda r: httpx.Response(404, content=b"secret internal page"),
        )
    assert str(exc_info.value) == "Download failed: remote returned HTTP 404"


def test_download_transport_error_is_generic(fake_dns, tmp_path: Path) -> None:
    fake_dns(PUBLIC_IP)

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused to 10.1.2.3:5432")

    with pytest.raises(DownloadError) as exc_info:
        _download("http://data.example/a.geojson", tmp_path / "out", handler)
    assert str(exc_info.value) == "Download failed"


# --- Upload path traversal and injection ----------------------------------


def _assert_uploads_are_server_named(settings: Settings) -> None:
    for path in settings.upload_dir.iterdir():
        assert len(path.stem) == 32
        assert all(c in "0123456789abcdef" for c in path.stem)


def test_upload_path_traversal(app, settings: Settings, sample_geojson: Path) -> None:
    resp = _upload(app, "../../evil.geojson", sample_geojson.read_bytes())
    assert resp.status_code == 200
    assert resp.json()["dataset_name"] == "evil"
    assert not (settings.data_dir.parent / "evil.geojson").exists()
    assert not (settings.data_dir / "evil.geojson").exists()
    _assert_uploads_are_server_named(settings)


def test_upload_absolute_path(app, settings: Settings, sample_geojson: Path) -> None:
    target = settings.data_dir.parent / "abs.geojson"
    resp = _upload(app, str(target), sample_geojson.read_bytes())
    assert resp.status_code == 200
    assert not target.exists()
    _assert_uploads_are_server_named(settings)


def test_upload_quote_injection(app, settings: Settings, sample_geojson: Path) -> None:
    resp = _upload(app, "a'b.geojson", sample_geojson.read_bytes())
    assert resp.status_code == 200
    assert resp.json()["dataset_name"] == "a_b"
    assert app.get("/api/datasets/a_b").status_code == 200
    _assert_uploads_are_server_named(settings)


def test_upload_unknown_extension(app, settings: Settings) -> None:
    resp = _upload(app, "evil.sh", b"#!/bin/sh\n")
    assert resp.status_code == 400
    assert list(settings.upload_dir.iterdir()) == []


def test_upload_size_cap(data_dir: Path) -> None:
    from fastapi.testclient import TestClient

    settings = Settings(data_dir=data_dir, max_upload_mb=1)
    with TestClient(create_app(settings)) as client:
        resp = _upload(client, "big.geojson", b"x" * (1024 * 1024 + 512 * 1024))
    assert resp.status_code == 413
    assert list(settings.upload_dir.iterdir()) == []


# --- from-url -------------------------------------------------------------


def test_from_url_rejects_name_injection(app) -> None:
    resp = app.post(
        "/api/ingest/from-url",
        json={"url": "http://example.com/x.geojson", "name": 'x"; DROP TABLE _datasets; --'},
    )
    assert resp.status_code == 422
    assert app.get("/api/datasets").status_code == 200


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1:8000/health.geojson",
        "http://169.254.169.254/latest/x.geojson",
        "http://10.0.0.5/internal.geojson",
        "file:///etc/passwd.geojson",
    ],
)
def test_from_url_blocks_ssrf(app, url: str) -> None:
    resp = app.post("/api/ingest/from-url", json={"url": url})
    assert resp.status_code == 400
    assert "not allowed" in resp.json()["detail"] or "http and https" in resp.json()["detail"]


def test_from_url_ingests_public(app, fake_dns, monkeypatch, sample_geojson: Path) -> None:
    fake_dns(PUBLIC_IP)
    body = sample_geojson.read_bytes()
    real_download = safe_fetch.download_to_file

    async def mocked(url: str, dest: Path, max_bytes: int) -> None:
        transport = httpx.MockTransport(lambda r: httpx.Response(200, content=body))
        await real_download(url, dest, max_bytes, transport=transport)

    monkeypatch.setattr("geo_app.routers.ingest.download_to_file", mocked)
    resp = app.post(
        "/api/ingest/from-url",
        json={"url": "https://data.example/places.geojson", "name": "places"},
    )
    assert resp.status_code == 200
    assert resp.json()["dataset_name"] == "places"
    assert resp.json()["feature_count"] == 3


# --- DuckDB sandbox -------------------------------------------------------


def test_duckdb_sandbox_blocks_outside_files(app) -> None:
    conn = app.app.state.db.conn
    with pytest.raises(duckdb.PermissionException):
        conn.execute("SELECT * FROM read_text('/etc/passwd')").fetchall()


def test_duckdb_sandbox_is_locked(app) -> None:
    conn = app.app.state.db.conn
    with pytest.raises(duckdb.Error):
        conn.execute("SET enable_external_access = true")


# --- Error leakage --------------------------------------------------------


def test_unknown_dataset_error_is_generic(app) -> None:
    resp = app.post("/api/query/nearest", json={"dataset": "nope", "lon": 0, "lat": 0})
    assert resp.status_code == 404
    assert resp.json() == {"detail": "Dataset or column not found"}


def test_unknown_column_error_is_generic(app, ingested_dataset: str) -> None:
    resp = app.post(
        "/api/query/filter",
        json={
            "dataset": ingested_dataset,
            "filters": [{"column": "missing_col", "op": "eq", "value": 1}],
        },
    )
    assert resp.status_code == 400
    assert resp.json() == {"detail": "Invalid query for this dataset"}


def test_corrupt_upload_does_not_leak_paths(app, settings: Settings) -> None:
    resp = _upload(app, "bad.geojson", b"{not json")
    assert resp.status_code == 400
    assert str(settings.data_dir) not in resp.text
    assert resp.json()["detail"] == "Could not read file as geojson"


def test_unhandled_error_is_generic(app_no_raise, settings: Settings, monkeypatch) -> None:
    def boom(*args, **kwargs):
        raise RuntimeError(f"boom {settings.data_dir}")

    monkeypatch.setattr("geo_app.routers.query.query_bbox", boom)
    resp = app_no_raise.get(
        "/api/query/bbox",
        params={"dataset": "x", "minx": 0, "miny": 0, "maxx": 1, "maxy": 1},
    )
    assert resp.status_code == 500
    assert resp.json() == {"detail": "Internal server error"}


# --- Read-only mode -------------------------------------------------------


def test_readonly_blocks_writes(readonly_app, sample_geojson: Path) -> None:
    assert _upload(readonly_app, "x.geojson", sample_geojson.read_bytes()).status_code == 403
    resp = readonly_app.post(
        "/api/ingest/from-url", json={"url": "https://data.example/x.geojson", "name": "x"}
    )
    assert resp.status_code == 403
    assert readonly_app.delete("/api/datasets/x").status_code == 403


def test_readonly_allows_reads(readonly_app) -> None:
    assert readonly_app.get("/api/datasets").status_code == 200
    assert readonly_app.get("/api/builtins/available").status_code == 200
    assert readonly_app.get("/health").json()["read_only"] is True


def test_default_is_writable(app) -> None:
    assert app.get("/health").json()["read_only"] is False


def test_builtin_load_is_idempotent(readonly_app, monkeypatch, sample_geojson: Path) -> None:
    calls: list[str] = []

    async def fake_download(url: str, dest: Path, max_bytes: int) -> None:
        calls.append(url)
        dest.write_bytes(sample_geojson.read_bytes())

    monkeypatch.setattr("geo_app.services.builtin_datasets.download_to_file", fake_download)
    for _ in range(2):
        resp = readonly_app.post("/api/builtins/load", json={"dataset": "ne-lakes-110m"})
        assert resp.status_code == 200
        assert resp.json()["dataset_name"] == "ne_lakes_110m"
        assert resp.json()["feature_count"] == 3
    assert len(calls) == 1


# --- Startup with legacy names -------------------------------------------


def test_reregister_skips_invalid_legacy_names(data_dir: Path, sample_geojson: Path) -> None:
    from fastapi.testclient import TestClient

    settings = Settings(data_dir=data_dir)
    with TestClient(create_app(settings)) as client:
        assert _upload(client, "good.geojson", sample_geojson.read_bytes()).status_code == 200

    # Simulate a row written before name validation existed
    conn = duckdb.connect(str(settings.duckdb_path))
    conn.execute("INSERT INTO _datasets (name) VALUES ('bad\"name')")
    conn.close()
    (settings.parquet_dir / 'bad"name.parquet').write_text(json.dumps({}))

    with TestClient(create_app(settings)) as client:
        assert client.get("/api/datasets/good/geojson").status_code == 200
        assert client.get("/health").status_code == 200
