from pipeline.sources import nws_alerts

def _feat(event):
    return {"features": [{"properties": {"event": event}}]}

def test_tornado_warning_cancels(monkeypatch):
    monkeypatch.setattr(nws_alerts.http, "get_json", lambda *a, **k: _feat("Tornado Warning"))
    out = nws_alerts.fetch(45.1, -93.4)
    assert "Tornado Warning" in out["cancel"]

def test_air_quality_alert_is_flag(monkeypatch):
    monkeypatch.setattr(nws_alerts.http, "get_json", lambda *a, **k: _feat("Air Quality Alert"))
    out = nws_alerts.fetch(45.1, -93.4)
    assert "Air Quality Alert" in out["flags"]
    assert out["cancel"] == []
