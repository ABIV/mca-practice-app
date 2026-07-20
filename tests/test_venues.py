import json, pathlib


def test_venues_schema():
    data = json.loads(pathlib.Path("venues.json").read_text())
    assert len(data) >= 2
    for v in data:
        assert set(v) >= {"id", "name", "short", "city", "lat", "lon", "metar"}
        assert -180 <= v["lon"] <= 180 and -90 <= v["lat"] <= 90
        ids = [x["id"] for x in data]
    assert len(ids) == len(set(ids))  # unique ids
