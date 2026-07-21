"""Open-Meteo HRRR: GHI + cloud + temp/RH/wind for current hour + 12 forecast hours.

fetch_many() batches all venues into ONE request. The per-venue architecture made
one call per venue; from GitHub Actions' shared runner IP that tripped Open-Meteo's
rate limit and a subset of calls 429'd, leaving those venues with no GHI (UNKNOWN).
One multi-location request is 18x fewer calls and stays under the limit.
"""
from datetime import datetime
from zoneinfo import ZoneInfo
from pipeline import http

CENTRAL = ZoneInfo("America/Chicago")
URL = "https://api.open-meteo.com/v1/forecast"
_HOURLY = ("shortwave_radiation,cloud_cover,temperature_2m,"
           "relative_humidity_2m,wind_speed_10m,precipitation_probability,weather_code")
_BASE = {"models": "ncep_hrrr_conus", "timezone": "America/Chicago", "forecast_hours": 13,
         "temperature_unit": "fahrenheit", "wind_speed_unit": "mph", "hourly": _HOURLY}
_LAT_TOL = 0.5  # identity guard: returned grid latitude must be within this of requested

def _parse_hours(h):
    hours = []
    for i, t in enumerate(h["time"]):
        def g(key, i=i):
            arr = h.get(key) or []
            return arr[i] if i < len(arr) else None
        hours.append({
            "time_iso": t, "ghi": g("shortwave_radiation"), "cloud_pct": g("cloud_cover"),
            "temp_f": g("temperature_2m"), "rh_pct": g("relative_humidity_2m"),
            "wind_mph": g("wind_speed_10m"), "precip_pct": g("precipitation_probability"),
            "weather_code": g("weather_code"),
        })
    return hours

def fetch(lat: float, lon: float) -> dict:
    data = http.get_json(URL, params={"latitude": lat, "longitude": lon, **_BASE})
    h = data.get("hourly")
    if not h or not h.get("time"):
        raise http.SourceError("Open-Meteo HRRR: empty hourly")
    return {"hours": _parse_hours(h), "fetched_at": datetime.now(CENTRAL).isoformat(timespec="seconds")}

def fetch_many(coords):
    """Fetch HRRR for many (lat, lon) in ONE request. Returns a list aligned to
    coords; each entry is {'hours': [...], 'fetched_at': ...} or None when that
    location's data is missing or fails the latitude identity guard — so a venue
    can never be handed another venue's data. Raises SourceError only if the whole
    request fails or returns the wrong number of locations."""
    if not coords:
        return []
    params = {"latitude": ",".join(str(c[0]) for c in coords),
              "longitude": ",".join(str(c[1]) for c in coords), **_BASE}
    data = http.get_json(URL, params=params)
    locs = data if isinstance(data, list) else [data]
    if len(locs) != len(coords):
        raise http.SourceError(f"Open-Meteo returned {len(locs)} locations, expected {len(coords)}")
    now_iso = datetime.now(CENTRAL).isoformat(timespec="seconds")
    out = []
    for (lat, lon), loc in zip(coords, locs):
        h = loc.get("hourly")
        rlat = loc.get("latitude")
        if not h or not h.get("time") or rlat is None or abs(rlat - lat) > _LAT_TOL:
            out.append(None)
        else:
            out.append({"hours": _parse_hours(h), "fetched_at": now_iso})
    return out
