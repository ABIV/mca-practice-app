import pytest
from pipeline import http

def test_user_agent_identifies_project():
    assert "mca-practice-app" in http.USER_AGENT

def test_get_json_raises_sourceerror_on_bad_status(monkeypatch):
    class FakeResp:
        status_code = 500
        def json(self): return {}
        text = "err"
    def fake_get(*a, **k): return FakeResp()
    monkeypatch.setattr(http.requests, "get", fake_get)
    with pytest.raises(http.SourceError):
        http.get_json("https://example.com")
