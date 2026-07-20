from pipeline.sources import airnow
from pipeline.http import SourceError
import pytest

CURRENT = [
  {"ReportingArea":"Minneapolis","Latitude":44.97,"Longitude":-93.26,"ParameterName":"O3","AQI":38,"Category":{"Name":"Good"}},
  {"ReportingArea":"Minneapolis","Latitude":44.97,"Longitude":-93.26,"ParameterName":"PM2.5","AQI":52,"Category":{"Name":"Moderate"}},
]
FORECAST = [
  {"DateForecast":"2026-07-19 ","ReportingArea":"Minneapolis","ParameterName":"PM2.5","AQI":76,"Category":{"Name":"Moderate"}},
]

def test_current_picks_dominant_pollutant(monkeypatch):
    monkeypatch.setattr(airnow.http, "get_json", lambda *a, **k: CURRENT)
    out = airnow.fetch_current(45.176, -93.430, "KEY")
    assert out["aqi"] == 52
    assert out["pollutant"] == "PM2.5"
    assert out["distance_mi"] > 0

def test_current_empty_raises(monkeypatch):
    monkeypatch.setattr(airnow.http, "get_json", lambda *a, **k: [])
    with pytest.raises(SourceError):
        airnow.fetch_current(45.176, -93.430, "KEY")

def test_forecast_negative_aqi_is_none(monkeypatch):
    monkeypatch.setattr(airnow.http, "get_json",
                        lambda *a, **k: [{"DateForecast":"x","ReportingArea":"A","ParameterName":"PM2.5","AQI":-1,"Category":{"Name":"None"}}])
    out = airnow.fetch_forecast(45.176, -93.430, "KEY")
    assert out["aqi"] is None
