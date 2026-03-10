def test_bbox_query(app, ingested_dataset):
    resp = app.get(
        "/api/query/bbox",
        params={
            "dataset": ingested_dataset,
            "minx": -1,
            "miny": -1,
            "maxx": 2,
            "maxy": 2,
        },
    )
    assert resp.status_code == 200
    fc = resp.json()
    assert fc["type"] == "FeatureCollection"
    # Should include Origin (0,0) and One-One (1,1), but not Ten-Ten (10,10)
    assert len(fc["features"]) == 2


def test_bbox_query_all(app, ingested_dataset):
    resp = app.get(
        "/api/query/bbox",
        params={
            "dataset": ingested_dataset,
            "minx": -180,
            "miny": -90,
            "maxx": 180,
            "maxy": 90,
        },
    )
    assert resp.status_code == 200
    fc = resp.json()
    assert len(fc["features"]) == 3


def test_nearest_query(app, ingested_dataset):
    resp = app.post(
        "/api/query/nearest",
        json={
            "dataset": ingested_dataset,
            "lon": 0.5,
            "lat": 0.5,
            "k": 2,
        },
    )
    assert resp.status_code == 200
    fc = resp.json()
    assert fc["type"] == "FeatureCollection"
    assert len(fc["features"]) == 2


def test_filter_query(app, ingested_dataset):
    resp = app.post(
        "/api/query/filter",
        json={
            "dataset": ingested_dataset,
            "filters": [{"column": "name", "op": "eq", "value": "Origin"}],
        },
    )
    assert resp.status_code == 200
    fc = resp.json()
    assert len(fc["features"]) == 1
    assert fc["features"][0]["properties"]["name"] == "Origin"


def test_filter_invalid_operator(app, ingested_dataset):
    resp = app.post(
        "/api/query/filter",
        json={
            "dataset": ingested_dataset,
            "filters": [{"column": "name", "op": "DROP TABLE", "value": "x"}],
        },
    )
    assert resp.status_code == 400
