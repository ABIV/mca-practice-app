"""Open-Meteo HRRR: GHI + cloud + temp/RH/wind for current hour + 12 forecast hours."""
from datetime import datetime
from zoneinfo import ZoneInfo
from pipeline import http

CENTRAL = ZoneInfo("America/Chicago")
URL = "https://api.open-meteo.com/v1/forecast"

def fetch(lat: float, lon: float) -> dict:
    params = {
        "latitude": lat, "longitude": lon, "models": "ncep_hrrr_conus",
        "timezone": "America/Chicago", "forecast_hours": 13,
        "temperature_unit": "fahrenheit", "wind_speed_unit": "mph",
        "hourly": ("shortwave_radiation,cloud_cover,temperature_2m,"
                   "relative_humidity_2m,wind_speed_10m,precipitation_probability,weather_code"),
    }
    data = http.get_json(URL, params=params)
    h = data.get("hourly")
    if not h or not h.get("time"):
        raise http.SourceError("Open-Meteo HRRR: empty hourly")
    hours = []
    for i, t in enumerate(h["time"]):
        def g(key):
            arr = h.get(key) or []
            return arr[i] if i < len(arr) else None
        hours.append({
            "time_iso": t,
            "ghi": g("shortwave_radiation"),
            "cloud_pct": g("cloud_cover"),
            "temp_f": g("temperature_2m"),
            "rh_pct": g("relative_humidity_2m"),
            "wind_mph": g("wind_speed_10m"),
            "precip_pct": g("precipitation_probability"),
            "weather_code": g("weather_code"),
        })
    return {"hours": hours, "fetched_at": datetime.now(CENTRAL).isoformat(timespec="seconds")}
