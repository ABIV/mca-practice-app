"""AirNow current observations (authoritative) + forecast (planning-grade)."""
from datetime import datetime
from zoneinfo import ZoneInfo
from pipeline import http, units

CENTRAL = ZoneInfo("America/Chicago")

# NOTE: these legacy `latLong` endpoints retire 2026-09-30. Before the first
# production run after that date, fetch https://docs.airnowapi.org/webservices,
# confirm the replacement paths ("Current Observations by Lat/Long or Zip",
# "Current Forecasts by Reporting Area") and their JSON shapes, and update
# _CUR/_FC and the parse keys below accordingly. Keep the dominant-pollutant
# + distance logic unchanged.
_CUR = "https://www.airnowapi.org/aq/observation/latLong/current/"
_FC = "https://www.airnowapi.org/aq/forecast/latLong/"

def fetch_current(lat, lon, api_key, distance=75) -> dict:
    params = {"format": "application/json", "latitude": lat, "longitude": lon,
              "distance": distance, "API_KEY": api_key}
    rows = http.get_json(_CUR, params=params)
    rows = [r for r in rows if isinstance(r.get("AQI"), int) and r["AQI"] >= 0]
    if not rows:
        raise http.SourceError("AirNow current: no observations")
    dom = max(rows, key=lambda r: r["AQI"])
    dist = units.haversine_mi(lat, lon, dom.get("Latitude", lat), dom.get("Longitude", lon))
    return {"aqi": dom["AQI"], "pollutant": dom.get("ParameterName", "?"),
            "reporting_area": dom.get("ReportingArea", "?"),
            "distance_mi": round(dist, 1),
            "category": dom.get("Category", {}).get("Name", "?"),
            "fetched_at": datetime.now(CENTRAL).isoformat(timespec="seconds")}

def fetch_forecast(lat, lon, api_key, date=None, distance=75) -> dict:
    params = {"format": "application/json", "latitude": lat, "longitude": lon,
              "distance": distance, "API_KEY": api_key}
    if date:
        params["date"] = date
    rows = http.get_json(_FC, params=params)
    valid = [r for r in rows if isinstance(r.get("AQI"), int) and r["AQI"] >= 0]
    if not valid:
        return {"aqi": None, "pollutant": None, "category": None, "reporting_area": None,
                "fetched_at": datetime.now(CENTRAL).isoformat(timespec="seconds")}
    dom = max(valid, key=lambda r: r["AQI"])
    return {"aqi": dom["AQI"], "pollutant": dom.get("ParameterName"),
            "category": dom.get("Category", {}).get("Name"),
            "reporting_area": dom.get("ReportingArea"),
            "fetched_at": datetime.now(CENTRAL).isoformat(timespec="seconds")}
