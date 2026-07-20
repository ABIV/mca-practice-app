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

def test_watch_is_not_cancel(monkeypatch):
    monkeypatch.setattr(nws_alerts.http, "get_json", lambda *a, **k: _feat("Severe Thunderstorm Watch"))
    out = nws_alerts.fetch(45.1, -93.4)
    assert out["cancel"] == []
    assert "Severe Thunderstorm Watch" in out["flags"]

def test_empty_features_ok(monkeypatch):
    monkeypatch.setattr(nws_alerts.http, "get_json", lambda *a, **k: {"features": []})
    out = nws_alerts.fetch(45.1, -93.4)
    assert out["cancel"] == [] and out["flags"] == []

def test_missing_event_skipped(monkeypatch):
    monkeypatch.setattr(nws_alerts.http, "get_json",
                        lambda *a, **k: {"features": [{"properties": {}}]})
    out = nws_alerts.fetch(45.1, -93.4)
    assert out["cancel"] == [] and out["flags"] == []
