"""Current observation from api.weather.gov METAR station."""
from datetime import datetime
from zoneinfo import ZoneInfo
from pipeline import http, units

CENTRAL = ZoneInfo("America/Chicago")

def fetch_current(station: str) -> dict:
    url = f"https://api.weather.gov/stations/{station}/observations/latest"
    data = http.get_json(url)
    p = data.get("properties", {})
    temp_c = p.get("temperature", {}).get("value")
    rh = p.get("relativeHumidity", {}).get("value")
    wind_kmh = p.get("windSpeed", {}).get("value")
    if temp_c is None or rh is None or wind_kmh is None:
        raise http.SourceError(f"METAR {station}: null temp/rh/wind")
    return {
        "temp_f": units.c_to_f(temp_c),
        "rh_pct": float(rh),
        "wind_mph": units.kmh_to_mph(wind_kmh),
        "station": station,
        "fetched_at": datetime.now(CENTRAL).isoformat(timespec="seconds"),
    }
