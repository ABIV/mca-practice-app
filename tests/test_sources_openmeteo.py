import json, pathlib
import pytest
from pipeline.sources import openmeteo
from pipeline.http import SourceError
FIX = pathlib.Path(__file__).parent / "fixtures" / "openmeteo_hrrr.json"

def test_parse_openmeteo(monkeypatch):
    data = json.loads(FIX.read_text())
    monkeypatch.setattr(openmeteo.http, "get_json", lambda *a, **k: data)
    out = openmeteo.fetch(45.176, -93.430)
    assert len(out["hours"]) >= 13
    h0 = out["hours"][0]
    assert set(h0) >= {"time_iso","ghi","cloud_pct","temp_f","rh_pct","wind_mph"}
    assert h0["ghi"] is not None

def test_empty_hourly_raises(monkeypatch):
    monkeypatch.setattr(openmeteo.http, "get_json", lambda *a, **k: {})
    with pytest.raises(SourceError):
        openmeteo.fetch(45.176, -93.430)

def test_empty_time_array_raises(monkeypatch):
    monkeypatch.setattr(openmeteo.http, "get_json",
                        lambda *a, **k: {"hourly": {"time": []}})
    with pytest.raises(SourceError):
        openmeteo.fetch(45.176, -93.430)

def _loc(lat, ghi0):
    return {"latitude": lat, "longitude": -93.0,
            "hourly": {"time": [f"2026-07-20T{h:02d}:00" for h in range(13)],
                       "shortwave_radiation": [ghi0] + [0.0] * 12, "cloud_cover": [10] * 13,
                       "temperature_2m": [80] * 13, "relative_humidity_2m": [50] * 13,
                       "wind_speed_10m": [5] * 13, "precipitation_probability": [0] * 13,
                       "weather_code": [1] * 13}}

def test_fetch_many_aligns_and_parses(monkeypatch):
    # Two locations returned as a list in input order; each venue gets its own data.
    monkeypatch.setattr(openmeteo.http, "get_json",
                        lambda *a, **k: [_loc(45.0, 111.0), _loc(46.0, 222.0)])
    out = openmeteo.fetch_many([(45.0, -93.0), (46.0, -93.0)])
    assert len(out) == 2
    assert out[0]["hours"][0]["ghi"] == 111.0
    assert out[1]["hours"][0]["ghi"] == 222.0  # not swapped/reused

def test_fetch_many_identity_guard(monkeypatch):
    # Returned latitude far from requested → None (never misassign one venue's data).
    monkeypatch.setattr(openmeteo.http, "get_json", lambda *a, **k: [_loc(10.0, 5.0)])
    assert openmeteo.fetch_many([(45.0, -93.0)]) == [None]

def test_fetch_many_length_mismatch_raises(monkeypatch):
    monkeypatch.setattr(openmeteo.http, "get_json", lambda *a, **k: [_loc(45.0, 5.0)])
    with pytest.raises(SourceError):
        openmeteo.fetch_many([(45.0, -93.0), (46.0, -93.0)])  # asked 2, got 1

def test_fetch_many_single_dict_response(monkeypatch):
    # A single-coordinate request can come back as a dict, not a list.
    monkeypatch.setattr(openmeteo.http, "get_json", lambda *a, **k: _loc(45.0, 7.0))
    out = openmeteo.fetch_many([(45.0, -93.0)])
    assert out[0]["hours"][0]["ghi"] == 7.0

def test_fetch_many_bad_location_is_none(monkeypatch):
    # A location with empty hourly → None entry, others still parse.
    monkeypatch.setattr(openmeteo.http, "get_json",
                        lambda *a, **k: [_loc(45.0, 9.0), {"latitude": 46.0, "hourly": {"time": []}}])
    out = openmeteo.fetch_many([(45.0, -93.0), (46.0, -93.0)])
    assert out[0]["hours"][0]["ghi"] == 9.0
    assert out[1] is None
