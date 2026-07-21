import json, pathlib
from pipeline.sources import metar
from pipeline.http import SourceError
import pytest

FIX = pathlib.Path(__file__).parent / "fixtures" / "metar_kmic.json"

def _obs(temp=None, rh=None, wind=None, wdir=None):
    return {"properties": {"temperature": {"value": temp},
                           "relativeHumidity": {"value": rh},
                           "windSpeed": {"value": wind},
                           "windDirection": {"value": wdir},
                           "timestamp": "2026-07-21T02:00:00+00:00"}}

def _obs_list(*obs):
    return {"features": list(obs)}

def test_parse_metar(monkeypatch):
    # metar_kmic.json is a single-observation payload; wrap it in the
    # observations-list shape the source now consumes.
    props = json.loads(FIX.read_text())["properties"]
    monkeypatch.setattr(metar.http, "get_json", lambda *a, **k: {"features": [{"properties": props}]})
    out = metar.fetch_current("KMIC")
    assert isinstance(out["temp_f"], float)
    assert 0 <= out["rh_pct"] <= 100
    assert out["wind_mph"] >= 0
    assert out["station"] == "KMIC"

def test_metar_all_null_temp_raises(monkeypatch):
    monkeypatch.setattr(metar.http, "get_json", lambda *a, **k: _obs_list(_obs(temp=None, rh=50, wind=10)))
    with pytest.raises(SourceError):
        metar.fetch_current("KMIC")

def test_metar_all_null_rh_raises(monkeypatch):
    # RH is a required thermal input; missing → unknown (cannot be assumed).
    monkeypatch.setattr(metar.http, "get_json", lambda *a, **k: _obs_list(_obs(temp=25, rh=None, wind=10)))
    with pytest.raises(SourceError):
        metar.fetch_current("KMIC")

def test_metar_null_wind_is_calm(monkeypatch):
    # NWS reports calm wind as null windSpeed (+null windDirection): valid data,
    # not missing — treat as 0 mph (conservative for WBGT: least cooling).
    monkeypatch.setattr(metar.http, "get_json",
        lambda *a, **k: _obs_list(_obs(temp=29, rh=45, wind=None, wdir=None)))
    out = metar.fetch_current("KSTP")
    assert out["wind_mph"] == 0.0
    assert round(out["temp_f"]) == 84  # 29C
    assert out["rh_pct"] == 45

def test_metar_skips_partial_latest_ob(monkeypatch):
    # The newest observation is a partial "special" (null temp/RH, wind only);
    # fall back to the most recent COMPLETE observation rather than failing.
    monkeypatch.setattr(metar.http, "get_json",
        lambda *a, **k: _obs_list(_obs(temp=None, rh=None, wind=13),   # partial special (newest)
                                  _obs(temp=25, rh=57, wind=8)))        # complete (older)
    out = metar.fetch_current("K21D")
    assert round(out["temp_f"]) == 77  # 25C
    assert out["rh_pct"] == 57
