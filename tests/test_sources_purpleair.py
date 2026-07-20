from pipeline.sources import purpleair
from pipeline.http import SourceError
import time, pytest

def _payload(rows):
    return {"fields": ["sensor_index","pm2.5_cf_1","humidity","confidence","last_seen","latitude","longitude"],
            "data": rows}

def test_nearest_corrected_and_aqi(monkeypatch):
    now = int(time.time())
    rows = [[101, 30.0, 50.0, 95, now, 45.18, -93.43],
            [102, 80.0, 40.0, 95, now, 45.28, -93.60]]  # farther + dirtier
    monkeypatch.setattr(purpleair.http, "get_json", lambda *a, **k: _payload(rows))
    out = purpleair.fetch_nearest(45.176, -93.430, "KEY")
    assert out["sensor_index"] == 101         # nearest wins
    assert out["pm25_corrected"] > 0
    assert 0 <= out["aqi"] <= 500

def test_all_stale_raises(monkeypatch):
    old = 0
    rows = [[101, 30.0, 50.0, 95, old, 45.18, -93.43]]
    monkeypatch.setattr(purpleair.http, "get_json", lambda *a, **k: _payload(rows))
    with pytest.raises(SourceError):
        purpleair.fetch_nearest(45.176, -93.430, "KEY")

def test_nearest_with_null_pm25_skipped(monkeypatch):
    now = int(time.time())
    # nearest sensor (101) has null pm2.5 -> should be skipped for farther valid 102
    rows = [[101, None, 50.0, 95, now, 45.18, -93.43],
            [102, 40.0, 45.0, 95, now, 45.30, -93.60]]
    monkeypatch.setattr(purpleair.http, "get_json", lambda *a, **k: _payload(rows))
    out = purpleair.fetch_nearest(45.176, -93.430, "KEY")
    assert out["sensor_index"] == 102
