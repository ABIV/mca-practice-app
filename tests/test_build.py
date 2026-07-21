import datetime
from zoneinfo import ZoneInfo
from pipeline import build
from pipeline.models import UNKNOWN, CANCELLED, CAUTION, GO

CENTRAL = ZoneInfo("America/Chicago")
VENUE = {"id":"wolly","name":"Woolly Trails","short":"Wolly","city":"St. Croix Falls, WI",
         "lat":45.395,"lon":-92.635,"metar":"KOEO"}

def _stub_sources(monkeypatch, *, airnow_aqi=40, fail=()):
    now = datetime.datetime(2026,7,19,17,0,tzinfo=CENTRAL)
    hours = [{"time_iso": (now+datetime.timedelta(hours=i)).isoformat(),
              "ghi": 400.0, "cloud_pct": 20, "temp_f": 85.0, "rh_pct": 40.0,
              "wind_mph": 6.0, "precip_pct": 10, "weather_code": 1} for i in range(13)]
    monkeypatch.setattr(build.metar, "fetch_current",
        lambda s: (_ for _ in ()).throw(build.http.SourceError("x")) if "metar" in fail
        else {"temp_f":85.0,"rh_pct":40.0,"wind_mph":6.0,"station":s,"fetched_at":"t"})
    monkeypatch.setattr(build.openmeteo, "fetch",
        lambda a,b: (_ for _ in ()).throw(build.http.SourceError("x")) if "openmeteo" in fail
        else {"hours":hours,"fetched_at":"t"})
    monkeypatch.setattr(build.nws_forecast, "fetch",
        lambda a,b: (_ for _ in ()).throw(build.http.SourceError("x")) if "nws" in fail
        else {"hours":[{**h,"short":"Sunny","is_storm":False} for h in hours[1:]],"fetched_at":"t"})
    monkeypatch.setattr(build.nws_alerts, "fetch",
        lambda a,b: (_ for _ in ()).throw(build.http.SourceError("x")) if "alerts" in fail
        else {"cancel":[],"flags":[],"fetched_at":"t"})
    monkeypatch.setattr(build.airnow, "fetch_current",
        lambda a,b,k,**kw: (_ for _ in ()).throw(build.http.SourceError("x")) if "airnow" in fail
        else {"aqi":airnow_aqi,"pollutant":"PM2.5","reporting_area":"A","distance_mi":5.0,"category":"Good","fetched_at":"t"})
    monkeypatch.setattr(build.airnow, "fetch_forecast", lambda a,b,k,**kw: {"aqi":50,"pollutant":"PM2.5","category":"Good","reporting_area":"A","fetched_at":"t"})
    monkeypatch.setattr(build.purpleair, "fetch_nearest",
        lambda a,b,k,**kw: {"aqi":45,"pm25_corrected":9.0,"sensor_index":1,"distance_mi":2.0,"fetched_at":"t"})
    return now

def test_build_venue_ok(monkeypatch):
    now = _stub_sources(monkeypatch)
    out = build.build_venue(VENUE, {"airnow":"K","purpleair":"K"}, now, [])
    assert out["venue_id"] == "wolly"
    assert len(out["hours"]) == 12
    assert out["status"] in ("GO","CAUTION","CANCELLED")

def test_build_venue_airnow_fail_caps_unknown(monkeypatch):
    now = _stub_sources(monkeypatch, fail=("airnow",))
    out = build.build_venue(VENUE, {"airnow":"K","purpleair":"K"}, now, [])
    assert out["status"] == UNKNOWN  # current AQI missing caps status

def test_build_venue_smoke_cancels(monkeypatch):
    now = _stub_sources(monkeypatch, airnow_aqi=187)
    out = build.build_venue(VENUE, {"airnow":"K","purpleair":"K"}, now, [])
    assert out["status"] == CANCELLED
    assert any("AQI Red (>150)" in r["detail"] for r in out["reasons"])

def test_alerts_failure_caps_unknown_and_flags(monkeypatch):
    now = _stub_sources(monkeypatch, fail=("alerts",))
    out = build.build_venue(VENUE, {"airnow": "K", "purpleair": "K"}, now, [])
    assert out["status"] == UNKNOWN
    assert any("alert check failed" in f for f in out["flags"])

def test_nws_forecast_failure_flags_hrrr_fallback(monkeypatch):
    now = _stub_sources(monkeypatch, fail=("nws",))
    out = build.build_venue(VENUE, {"airnow": "K", "purpleair": "K"}, now, [])
    assert len(out["hours"]) == 12  # still full strip from HRRR
    assert any("NWS hourly forecast unavailable" in f for f in out["flags"])

def test_openmeteo_failure_yields_unknown_hours(monkeypatch):
    now = _stub_sources(monkeypatch, fail=("openmeteo",))
    out = build.build_venue(VENUE, {"airnow": "K", "purpleair": "K"}, now, [])
    assert len(out["hours"]) == 12
    assert all(h["status"] == UNKNOWN for h in out["hours"])

def test_build_venue_nws_cross_format_hour_match(monkeypatch):
    """Open-Meteo returns time_iso with no seconds/offset ("...T11:00"); NWS
    returns time_iso with seconds+UTC-offset ("...T11:00:00-05:00") for the
    SAME local hour. If build.py matched forecast hours by exact string
    equality, the NWS hour (carrying is_storm=True) would never be found and
    its storm flag would never reach the policy evaluation for that hour.
    This test locks in the [:13] hour-prefix match fix."""
    now = datetime.datetime(2026, 7, 19, 17, 0, tzinfo=CENTRAL)
    hours = [{"time_iso": (now + datetime.timedelta(hours=i)).strftime("%Y-%m-%dT%H:00"),
              "ghi": 400.0, "cloud_pct": 20, "temp_f": 85.0, "rh_pct": 40.0,
              "wind_mph": 6.0, "precip_pct": 10, "weather_code": 1} for i in range(13)]

    def _nws_fetch(a, b):
        nws_hours = []
        for i, h in enumerate(hours[1:], start=1):
            dt = now + datetime.timedelta(hours=i)
            offset_iso = dt.strftime("%Y-%m-%dT%H:00:00-05:00")
            nws_hours.append({
                **h,
                "time_iso": offset_iso,
                "short": "Thunderstorms" if i == 1 else "Sunny",
                "is_storm": i == 1,
            })
        return {"hours": nws_hours, "fetched_at": "t"}

    monkeypatch.setattr(build.metar, "fetch_current",
        lambda s: {"temp_f":85.0,"rh_pct":40.0,"wind_mph":6.0,"station":s,"fetched_at":"t"})
    monkeypatch.setattr(build.openmeteo, "fetch", lambda a,b: {"hours":hours,"fetched_at":"t"})
    monkeypatch.setattr(build.nws_forecast, "fetch", _nws_fetch)
    monkeypatch.setattr(build.nws_alerts, "fetch", lambda a,b: {"cancel":[],"flags":[],"fetched_at":"t"})
    monkeypatch.setattr(build.airnow, "fetch_current",
        lambda a,b,k,**kw: {"aqi":40,"pollutant":"PM2.5","reporting_area":"A","distance_mi":5.0,"category":"Good","fetched_at":"t"})
    monkeypatch.setattr(build.airnow, "fetch_forecast", lambda a,b,k,**kw: {"aqi":50,"pollutant":"PM2.5","category":"Good","reporting_area":"A","fetched_at":"t"})
    monkeypatch.setattr(build.purpleair, "fetch_nearest",
        lambda a,b,k,**kw: {"aqi":45,"pm25_corrected":9.0,"sensor_index":1,"distance_mi":2.0,"fetched_at":"t"})

    out = build.build_venue(VENUE, {"airnow":"K","purpleair":"K"}, now, [])
    first_hour = out["hours"][0]
    assert first_hour["status"] in (CAUTION, CANCELLED)
    assert any(r["rule"] == "storm_forecast" for r in first_hour["reasons"])


def _stub_for_build_all(monkeypatch):
    monkeypatch.setattr(build.metar, "fetch_current",
        lambda s: {"temp_f":85.0,"rh_pct":40.0,"wind_mph":6.0,"station":s,"fetched_at":"t"})
    monkeypatch.setattr(build.nws_forecast, "fetch", lambda a,b: {"hours":[],"fetched_at":"t"})
    monkeypatch.setattr(build.nws_alerts, "fetch", lambda a,b: {"cancel":[],"flags":[],"fetched_at":"t"})
    monkeypatch.setattr(build.airnow, "fetch_current",
        lambda a,b,k,**kw: {"aqi":40,"pollutant":"PM2.5","reporting_area":"A","distance_mi":5.0,"category":"Good","fetched_at":"t"})
    monkeypatch.setattr(build.airnow, "fetch_forecast",
        lambda a,b,k,**kw: {"aqi":50,"pollutant":"PM2.5","category":"Good","reporting_area":"A","fetched_at":"t"})
    monkeypatch.setattr(build.purpleair, "fetch_nearest",
        lambda a,b,k,**kw: {"aqi":45,"pm25_corrected":9.0,"sensor_index":1,"distance_mi":2.0,"fetched_at":"t"})
    monkeypatch.setattr(build.schedule, "fetch_today", lambda venues, now=None: [])

def _om_slice(now, ghi):
    hrs = [{"time_iso":(now+datetime.timedelta(hours=i)).strftime("%Y-%m-%dT%H:00"),
            "ghi":ghi,"cloud_pct":10,"temp_f":85.0,"rh_pct":40.0,"wind_mph":6.0,
            "precip_pct":10,"weather_code":1} for i in range(13)]
    return {"hours":hrs,"fetched_at":"t"}

def test_build_all_batches_om_and_isolates(monkeypatch):
    now = datetime.datetime(2026,7,20,17,0,tzinfo=CENTRAL)
    _stub_for_build_all(monkeypatch)
    venues = [{"id":"a","name":"A","short":"A","city":"X","lat":45.0,"lon":-93.0,"metar":"KAAA"},
              {"id":"b","name":"B","short":"B","city":"Y","lat":46.0,"lon":-93.5,"metar":"KBBB"}]
    calls = {}
    def fake_many(coords):
        calls["coords"] = list(coords)
        return [_om_slice(now,111.0), _om_slice(now,222.0)]
    monkeypatch.setattr(build.openmeteo, "fetch_many", fake_many)
    out = build.build_all(venues, {"airnow":"K","purpleair":"K"}, now=now)
    assert calls["coords"] == [(45.0,-93.0),(46.0,-93.5)]  # exactly ONE batched call
    byid = {v["venue_id"]: v for v in out["venues"]}
    assert byid["a"]["current"]["ghi"]["value"] == 111.0   # each venue gets its OWN slice
    assert byid["b"]["current"]["ghi"]["value"] == 222.0   # not swapped or reused

def test_practice_hours_use_forecast_aqi_not_current(monkeypatch):
    # Current AQI benign (GO); forecast AQI hazardous (>150). The current status
    # uses current AQI; the forecast/practice hours use the forecast AQI.
    now = datetime.datetime(2026, 7, 20, 17, 0, tzinfo=CENTRAL)
    hours = [{"time_iso":(now+datetime.timedelta(hours=i)).strftime("%Y-%m-%dT%H:00"),
              "ghi":100.0,"cloud_pct":20,"temp_f":70.0,"rh_pct":40.0,"wind_mph":6.0,
              "precip_pct":10,"weather_code":1} for i in range(13)]
    monkeypatch.setattr(build.metar, "fetch_current",
        lambda s: {"temp_f":70.0,"rh_pct":40.0,"wind_mph":6.0,"station":s,"fetched_at":"t"})
    monkeypatch.setattr(build.openmeteo, "fetch", lambda a,b: {"hours":hours,"fetched_at":"t"})
    monkeypatch.setattr(build.nws_forecast, "fetch",
        lambda a,b: {"hours":[{**h,"short":"Sunny","is_storm":False} for h in hours[1:]],"fetched_at":"t"})
    monkeypatch.setattr(build.nws_alerts, "fetch", lambda a,b: {"cancel":[],"flags":[],"fetched_at":"t"})
    monkeypatch.setattr(build.airnow, "fetch_current",
        lambda a,b,k,**kw: {"aqi":40,"pollutant":"PM2.5","reporting_area":"A","distance_mi":5.0,"category":"Good","fetched_at":"t"})
    monkeypatch.setattr(build.airnow, "fetch_forecast",
        lambda a,b,k,**kw: {"aqi":160,"pollutant":"PM2.5","category":"Unhealthy","reporting_area":"A","fetched_at":"t"})
    monkeypatch.setattr(build.purpleair, "fetch_nearest",
        lambda a,b,k,**kw: {"aqi":40,"pm25_corrected":9.0,"sensor_index":1,"distance_mi":2.0,"fetched_at":"t"})
    out = build.build_venue(VENUE, {"airnow":"K","purpleair":"K"}, now, [])
    assert out["status"] == "GO"                                    # current uses current AQI 40
    assert all(h["status"] == CANCELLED for h in out["hours"])      # forecast hours use forecast AQI 160

def test_build_all_om_batch_failure_caps_all_unknown(monkeypatch):
    now = datetime.datetime(2026,7,20,17,0,tzinfo=CENTRAL)
    _stub_for_build_all(monkeypatch)
    venues = [{"id":"a","name":"A","short":"A","city":"X","lat":45.0,"lon":-93.0,"metar":"KAAA"}]
    monkeypatch.setattr(build.openmeteo, "fetch_many",
        lambda coords: (_ for _ in ()).throw(build.http.SourceError("rate limit")))
    out = build.build_all(venues, {"airnow":"K","purpleair":"K"}, now=now)
    v = out["venues"][0]
    assert v["current"]["ghi"]["status"] == "unknown"
    assert v["status"] == "UNKNOWN"
