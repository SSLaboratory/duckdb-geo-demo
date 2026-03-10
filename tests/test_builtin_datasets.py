from geo_app.services.builtin_datasets import find_builtin, get_available


def test_list_available():
    available = get_available()
    assert len(available) >= 4
    ids = [d.id for d in available]
    assert "ne-countries-110m" in ids


def test_find_builtin():
    ds = find_builtin("ne-countries-110m")
    assert ds is not None
    assert ds.name == "Natural Earth Countries (110m)"


def test_find_builtin_not_found():
    ds = find_builtin("nonexistent")
    assert ds is None


def test_available_endpoint(app):
    resp = app.get("/api/builtins/available")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 4
