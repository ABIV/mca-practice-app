import json, pathlib
from pipeline.sources import metar
from pipeline.http import SourceError
import pytest

FIX = pathlib.Path(__file__).parent / "fixtures" / "metar_kmic.json"

def test_parse_metar(monkeypatch):
    data = json.loads(FIX.read_text())
    monkeypatch.setattr(metar.http, "get_json", lambda *a, **k: data)
    out = metar.fetch_current("KMIC")
    assert isinstance(out["temp_f"], float)
    assert 0 <= out["rh_pct"] <= 100
    assert out["wind_mph"] >= 0
    assert out["station"] == "KMIC"

def test_metar_null_temp_raises(monkeypatch):
    bad = {"properties": {"temperature": {"value": None},
                          "relativeHumidity": {"value": 50},
                          "windSpeed": {"value": 10}, "timestamp": "2026-07-19T19:00:00+00:00"}}
    monkeypatch.setattr(metar.http, "get_json", lambda *a, **k: bad)
    with pytest.raises(SourceError):
        metar.fetch_current("KMIC")

def test_metar_null_rh_raises(monkeypatch):
    # RH is a required thermal input; missing → unknown (cannot be assumed).
    bad = {"properties": {"temperature": {"value": 25},
                          "relativeHumidity": {"value": None},
                          "windSpeed": {"value": 10}, "timestamp": "2026-07-19T19:00:00+00:00"}}
    monkeypatch.setattr(metar.http, "get_json", lambda *a, **k: bad)
    with pytest.raises(SourceError):
        metar.fetch_current("KMIC")

def test_metar_null_wind_is_calm(monkeypatch):
    # NWS reports calm wind as null windSpeed (+null windDirection). This is a
    # valid observation, NOT missing data — treat as 0 mph (calm), which is also
    # the conservative direction for WBGT (least cooling → highest WBGT).
    calm = {"properties": {"temperature": {"value": 29}, "relativeHumidity": {"value": 45},
                           "windSpeed": {"value": None}, "windDirection": {"value": None},
                           "timestamp": "2026-07-21T01:10:00+00:00"}}
    monkeypatch.setattr(metar.http, "get_json", lambda *a, **k: calm)
    out = metar.fetch_current("KSTP")
    assert out["wind_mph"] == 0.0
    assert round(out["temp_f"]) == 84  # 29C
    assert out["rh_pct"] == 45
