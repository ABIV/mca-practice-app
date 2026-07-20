"""Nearest outdoor PurpleAir sensor with EPA/Barkjohn correction -> AQI."""
import math
import time
from datetime import datetime
from zoneinfo import ZoneInfo
from pipeline import http, units, aqi

CENTRAL = ZoneInfo("America/Chicago")
URL = "https://api.purpleair.com/v1/sensors"
MAX_AGE_S = 2 * 3600
MIN_CONFIDENCE = 70

def fetch_nearest(lat, lon, api_key, radius_mi=15) -> dict:
    dlat = radius_mi / 69.0
    dlon = radius_mi / (69.0 * max(0.1, abs(math.cos(math.radians(lat)))))
    params = {"fields": "pm2.5_cf_1,humidity,confidence,last_seen,latitude,longitude",
              "location_type": 0,
              "nwlng": lon - dlon, "nwlat": lat + dlat,
              "selng": lon + dlon, "selat": lat - dlat}
    data = http.get_json(URL, params=params, headers={"X-API-Key": api_key})
    fields = data.get("fields", [])
    idx = {name: i for i, name in enumerate(fields)}
    now = int(time.time())
    best = None
    for row in data.get("data", []):
        try:
            conf = row[idx["confidence"]]
            seen = row[idx["last_seen"]]
            slat, slon = row[idx["latitude"]], row[idx["longitude"]]
        except (KeyError, IndexError):
            continue
        if conf is None or conf < MIN_CONFIDENCE:
            continue
        if seen is None or (now - seen) > MAX_AGE_S:
            continue
        pa = row[idx["pm2.5_cf_1"]]
        if pa is None:
            continue
        dist = units.haversine_mi(lat, lon, slat, slon)
        if best is None or dist < best[0]:
            best = (dist, row)
    if best is None:
        raise http.SourceError("PurpleAir: no fresh, confident sensor nearby")
    dist, row = best
    pa = row[idx["pm2.5_cf_1"]]
    # A sensor reporting null humidity still needs an RH input for the Barkjohn
    # correction, so fall back to a neutral default of 50% RH.
    rh = row[idx["humidity"]] if row[idx["humidity"]] is not None else 50.0
    corrected = aqi.barkjohn_correct(pa, rh)
    return {"aqi": aqi.pm25_to_aqi(corrected), "pm25_corrected": round(corrected, 1),
            "sensor_index": row[idx["sensor_index"]] if "sensor_index" in idx else None,
            "distance_mi": round(dist, 1),
            "fetched_at": datetime.now(CENTRAL).isoformat(timespec="seconds")}
