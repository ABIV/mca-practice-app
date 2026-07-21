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
    # Temp and RH are required thermal inputs — a null means genuinely missing
    # data and the reading is unusable (WBGT → UNKNOWN).
    if temp_c is None or rh is None:
        raise http.SourceError(f"METAR {station}: null temp/RH")
    # NWS reports CALM wind as null windSpeed (with null windDirection), which is
    # a valid observation, not missing data. Treat null wind as 0 mph (calm) —
    # also the conservative direction for WBGT, since less wind means less
    # cooling and thus a higher (safer) heat-stress estimate.
    wind_mph = units.kmh_to_mph(wind_kmh) if wind_kmh is not None else 0.0
    return {
        "temp_f": units.c_to_f(temp_c),
        "rh_pct": float(rh),
        "wind_mph": wind_mph,
        "station": station,
        "fetched_at": datetime.now(CENTRAL).isoformat(timespec="seconds"),
    }
