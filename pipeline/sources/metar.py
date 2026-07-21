"""Current observation from api.weather.gov METAR station."""
from datetime import datetime
from zoneinfo import ZoneInfo
from pipeline import http, units

CENTRAL = ZoneInfo("America/Chicago")

def fetch_current(station: str) -> dict:
    # Use the observations LIST (newest first), not /observations/latest. The
    # "latest" endpoint intermittently returns a partial "special" report with
    # null temp/RH (e.g. a wind-only ob), which would spuriously fail. Scan the
    # recent obs and use the most recent COMPLETE one (temp + RH present).
    url = f"https://api.weather.gov/stations/{station}/observations?limit=8"
    data = http.get_json(url)
    for feat in data.get("features", []):
        p = feat.get("properties", {})
        temp_c = p.get("temperature", {}).get("value")
        rh = p.get("relativeHumidity", {}).get("value")
        # Temp and RH are required thermal inputs; a null means this ob is partial
        # — skip it and try the next (older) observation.
        if temp_c is None or rh is None:
            continue
        wind_kmh = p.get("windSpeed", {}).get("value")
        # NWS reports CALM wind as null windSpeed (with null windDirection): valid
        # data, not missing. Treat null wind as 0 mph (calm) — also the
        # conservative direction for WBGT (less wind → less cooling → higher heat).
        wind_mph = units.kmh_to_mph(wind_kmh) if wind_kmh is not None else 0.0
        return {
            "temp_f": units.c_to_f(temp_c),
            "rh_pct": float(rh),
            "wind_mph": wind_mph,
            "station": station,
            "fetched_at": datetime.now(CENTRAL).isoformat(timespec="seconds"),
        }
    raise http.SourceError(f"METAR {station}: no recent observation with temp/RH")
