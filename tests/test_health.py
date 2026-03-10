def test_health(app):
    resp = app.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["spatial_loaded"] is True
    assert "duckdb_version" in data
    assert data["dataset_count"] == 0
