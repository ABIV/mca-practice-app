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
