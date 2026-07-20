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
