"""NWS forecastHourly (National Blend of Models) — next 12 hours."""
import re
from datetime import datetime
from zoneinfo import ZoneInfo
from pipeline import http

CENTRAL = ZoneInfo("America/Chicago")

def _wind_mph(s):
    m = re.search(r"(\d+)", s or "")
    return float(m.group(1)) if m else 0.0

def fetch(lat: float, lon: float) -> dict:
    pts = http.get_json(f"https://api.weather.gov/points/{lat},{lon}")
    hourly_url = pts.get("properties", {}).get("forecastHourly")
    if not hourly_url:
        raise http.SourceError("NWS points: no forecastHourly URL")
    fc = http.get_json(hourly_url)
    periods = fc.get("properties", {}).get("periods", [])
    if not periods:
        raise http.SourceError("NWS forecastHourly: no periods")
    hours = []
    for p in periods[:12]:
        short = p.get("shortForecast", "")
        hours.append({
            "time_iso": p.get("startTime"),
            "temp_f": float(p.get("temperature")) if p.get("temperature") is not None else None,
            "rh_pct": (p.get("relativeHumidity") or {}).get("value"),
            "wind_mph": _wind_mph(p.get("windSpeed")),
            "precip_pct": (p.get("probabilityOfPrecipitation") or {}).get("value"),
            "short": short,
            "is_storm": "thunder" in short.lower(),
        })
    return {"hours": hours, "fetched_at": datetime.now(CENTRAL).isoformat(timespec="seconds")}
