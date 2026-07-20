import json, pathlib
from pipeline.sources import nws_forecast
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
