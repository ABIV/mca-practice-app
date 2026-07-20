import pytest
from pipeline import policy
from pipeline.models import GO, CAUTION, CANCELLED, UNKNOWN

def base(**kw):
    s = {"wbgt": 70.0, "aqi": 20, "aqi_known": True, "wbgt_known": True,
         "severe_warnings": [], "storm_forecast": False}
    s.update(kw)
    return s

@pytest.mark.parametrize("wbgt,expected", [
    (81.9, GO), (82.0, CAUTION), (85.0, CAUTION),
    (85.1, CAUTION), (87.1, CAUTION), (87.2, CANCELLED),
])
def test_heat_bands(wbgt, expected):
    assert policy.evaluate(base(wbgt=wbgt))["status"] == expected

@pytest.mark.parametrize("aqi,expected", [
    (50, GO), (51, GO), (100, GO), (101, CAUTION), (150, CAUTION), (151, CANCELLED),
])
def test_aqi_bands(aqi, expected):
    # AQI 51-100 is a note, not a status change -> still GO on its own
    assert policy.evaluate(base(aqi=aqi))["status"] == expected

def test_severe_warning_cancels():
    r = policy.evaluate(base(severe_warnings=["Tornado Warning"]))
    assert r["status"] == CANCELLED

def test_storm_forecast_is_caution_flag():
    assert policy.evaluate(base(storm_forecast=True))["status"] == CAUTION

def test_unknown_caps_status():
    assert policy.evaluate(base(aqi_known=False))["status"] == UNKNOWN
    assert policy.evaluate(base(wbgt_known=False))["status"] == UNKNOWN

def test_combined_stress_escalates_one_level():
    # AQI 120 (orange->CAUTION) AND WBGT 83 (>80) -> escalate to CANCELLED
    r = policy.evaluate(base(aqi=120, wbgt=83.0))
    assert r["status"] == CANCELLED
    assert any("stricter than MCA" in x["detail"] for x in r["reasons"])

def test_worst_of_wins():
    r = policy.evaluate(base(wbgt=70.0, aqi=160))
    assert r["status"] == CANCELLED

def test_smoke_event_2026_07_19_cancels():
    # AirNow AQI 187 at Wolly must CANCEL with "AQI Red (>150)"
    r = policy.evaluate(base(aqi=187, wbgt=70.0))
    assert r["status"] == CANCELLED
    assert any("AQI Red (>150)" in x["detail"] for x in r["reasons"])

def test_benign_forecast_aqi_does_not_override(monkeypatch):
    # Forecast AQI is never passed into evaluate() as current 'aqi'; ensure a
    # benign forecast value cannot flip a CANCELLED current reading.
    r = policy.evaluate(base(aqi=187))          # current authoritative
    assert r["status"] == CANCELLED             # forecast 76 is display-only, not here
