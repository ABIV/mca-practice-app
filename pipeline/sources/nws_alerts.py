"""NWS active alerts → CANCEL warnings vs informational flags."""
from datetime import datetime
from zoneinfo import ZoneInfo
from pipeline import http

CENTRAL = ZoneInfo("America/Chicago")
_CANCEL = {"Severe Thunderstorm Warning", "Tornado Warning", "Flash Flood Warning"}

def fetch(lat: float, lon: float) -> dict:
    data = http.get_json("https://api.weather.gov/alerts/active", params={"point": f"{lat},{lon}"})
    cancel, flags = [], []
    for f in data.get("features", []):
        ev = f.get("properties", {}).get("event", "")
        if not ev:
            continue
        (cancel if ev in _CANCEL else flags).append(ev)
    return {"cancel": cancel, "flags": flags,
            "fetched_at": datetime.now(CENTRAL).isoformat(timespec="seconds")}
