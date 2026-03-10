def test_upload_geojson(app, sample_geojson):
    with open(sample_geojson, "rb") as f:
        resp = app.post("/api/ingest/upload", files={"file": ("test.geojson", f)})
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["dataset_name"] == "test"
    assert data["feature_count"] == 3


def test_upload_csv(app, sample_csv):
    with open(sample_csv, "rb") as f:
        resp = app.post("/api/ingest/upload", files={"file": ("locations.csv", f)})
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["dataset_name"] == "locations"
    assert data["feature_count"] == 3


def test_upload_no_filename(app):
    resp = app.post("/api/ingest/upload", files={"file": ("", b"")})
    assert resp.status_code in (400, 422)


def test_dataset_listed_after_upload(app, sample_geojson):
    with open(sample_geojson, "rb") as f:
        app.post("/api/ingest/upload", files={"file": ("sample.geojson", f)})

    resp = app.get("/api/datasets")
    assert resp.status_code == 200
    data = resp.json()
    assert data["count"] == 1
    assert data["datasets"][0]["name"] == "sample"


def test_dataset_geojson_endpoint(app, sample_geojson):
    with open(sample_geojson, "rb") as f:
        app.post("/api/ingest/upload", files={"file": ("sample.geojson", f)})

    resp = app.get("/api/datasets/sample/geojson")
    assert resp.status_code == 200
    fc = resp.json()
    assert fc["type"] == "FeatureCollection"
    assert len(fc["features"]) == 3


def test_dataset_detail(app, sample_geojson):
    with open(sample_geojson, "rb") as f:
        app.post("/api/ingest/upload", files={"file": ("sample.geojson", f)})

    resp = app.get("/api/datasets/sample")
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "sample"
    assert data["feature_count"] == 3


def test_dataset_not_found(app):
    resp = app.get("/api/datasets/nonexistent")
    assert resp.status_code == 404


def test_delete_dataset(app, sample_geojson):
    with open(sample_geojson, "rb") as f:
        app.post("/api/ingest/upload", files={"file": ("sample.geojson", f)})

    resp = app.delete("/api/datasets/sample")
    assert resp.status_code == 200

    resp = app.get("/api/datasets/sample")
    assert resp.status_code == 404
