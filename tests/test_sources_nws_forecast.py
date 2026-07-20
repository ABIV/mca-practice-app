import json, pathlib
import pytest
from pipeline.sources import nws_forecast
from pipeline.http import SourceError
FX = pathlib.Path(__file__).parent / "fixtures"

def test_parse_nws_hourly(monkeypatch):
    points = json.loads((FX / "nws_points.json").read_text())
    hourly = json.loads((FX / "nws_hourly.json").read_text())
    calls = {"n": 0}
    def fake(url, *a, **k):
        calls["n"] += 1
        # NWS forecastHourly URLs live under /gridpoints/, which contains the
        # substring "points" — so a plain `"points" in url` check can't tell
        # the two calls apart. Discriminate by call order instead.
        return points if calls["n"] == 1 else hourly
    monkeypatch.setattr(nws_forecast.http, "get_json", fake)
    out = nws_forecast.fetch(45.176, -93.430)
    assert len(out["hours"]) == 12
    h0 = out["hours"][0]
    assert isinstance(h0["temp_f"], (int, float))
    assert "is_storm" in h0


def test_missing_forecast_hourly_url_raises(monkeypatch):
    monkeypatch.setattr(nws_forecast.http, "get_json",
                        lambda url, *a, **k: {"properties": {}})
    with pytest.raises(SourceError):
        nws_forecast.fetch(45.176, -93.430)

def test_empty_periods_raises(monkeypatch):
    def fake(url, *a, **k):
        if "points" in url and "gridpoints" not in url:
            return {"properties": {"forecastHourly": "https://api.weather.gov/gridpoints/MPX/1,1/forecast/hourly"}}
        return {"properties": {"periods": []}}
    monkeypatch.setattr(nws_forecast.http, "get_json", fake)
    with pytest.raises(SourceError):
        nws_forecast.fetch(45.176, -93.430)

def test_is_storm_true_for_thunderstorm(monkeypatch):
    def fake(url, *a, **k):
        if "points" in url and "gridpoints" not in url:
            return {"properties": {"forecastHourly": "https://api.weather.gov/gridpoints/MPX/1,1/forecast/hourly"}}
        return {"properties": {"periods": [{
            "startTime": "2026-07-20T17:00:00-05:00", "temperature": 85,
            "relativeHumidity": {"value": 60}, "windSpeed": "10 mph",
            "probabilityOfPrecipitation": {"value": 70},
            "shortForecast": "Thunderstorms Likely"}]}}
    monkeypatch.setattr(nws_forecast.http, "get_json", fake)
    out = nws_forecast.fetch(45.176, -93.430)
    assert out["hours"][0]["is_storm"] is True
