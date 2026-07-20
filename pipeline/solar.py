"""Solar geometry via NOAA equations using true solar time.

Clear-sky GHI uses a simple air-mass model; it is used ONLY for the
'solar suspect' sanity check, never to clamp measured/forecast GHI.
"""
import math
from datetime import datetime, timezone

def _julian_day(dt_utc: datetime) -> float:
    dt = dt_utc.astimezone(timezone.utc)
    y, m = dt.year, dt.month
    d = dt.day + (dt.hour + dt.minute / 60 + dt.second / 3600) / 24.0
    if m <= 2:
        y -= 1
        m += 12
    a = y // 100
    b = 2 - a + a // 4
    return int(365.25 * (y + 4716)) + int(30.6001 * (m + 1)) + d + b - 1524.5

def solar_elevation_deg(dt_utc: datetime, lat: float, lon: float) -> float:
    if dt_utc.tzinfo is None or dt_utc.utcoffset() is None:
        raise ValueError(
            "solar_elevation_deg requires a timezone-aware datetime (dt_utc); "
            "got a naive datetime, which Python would silently interpret in the "
            "local system timezone. Pass a datetime with tzinfo set (e.g. "
            "datetime(..., tzinfo=timezone.utc))."
        )
    jd = _julian_day(dt_utc)
    t = (jd - 2451545.0) / 36525.0  # Julian centuries
    # Geometric mean longitude & anomaly of the sun (deg)
    L0 = (280.46646 + t * (36000.76983 + t * 0.0003032)) % 360
    M = 357.52911 + t * (35999.05029 - 0.0001537 * t)
    # Sun's equation of center
    C = (math.sin(math.radians(M)) * (1.914602 - t * (0.004817 + 0.000014 * t))
         + math.sin(math.radians(2 * M)) * (0.019993 - 0.000101 * t)
         + math.sin(math.radians(3 * M)) * 0.000289)
    true_long = L0 + C
    omega = 125.04 - 1934.136 * t
    lam = true_long - 0.00569 - 0.00478 * math.sin(math.radians(omega))
    # Obliquity of the ecliptic
    seconds = 21.448 - t * (46.8150 + t * (0.00059 - t * 0.001813))
    eps0 = 23.0 + (26.0 + seconds / 60.0) / 60.0
    eps = eps0 + 0.00256 * math.cos(math.radians(omega))
    decl = math.degrees(math.asin(math.sin(math.radians(eps)) * math.sin(math.radians(lam))))
    # Equation of time (minutes)
    y = math.tan(math.radians(eps / 2)) ** 2
    eot = 4 * math.degrees(
        y * math.sin(2 * math.radians(L0))
        - 2 * 0.016708634 * math.sin(math.radians(M))
        + 4 * 0.016708634 * y * math.sin(math.radians(M)) * math.cos(2 * math.radians(L0))
        - 0.5 * y * y * math.sin(4 * math.radians(L0))
        - 1.25 * 0.016708634 ** 2 * math.sin(2 * math.radians(M))
    )
    dt = dt_utc.astimezone(timezone.utc)
    minutes = dt.hour * 60 + dt.minute + dt.second / 60.0
    # True solar time (minutes): clock UTC + EoT + longitude correction (4 min/deg)
    tst = (minutes + eot + 4 * lon) % 1440
    ha = tst / 4.0 - 180.0  # hour angle, deg
    phi = math.radians(lat)
    d = math.radians(decl)
    cos_zen = (math.sin(phi) * math.sin(d)
               + math.cos(phi) * math.cos(d) * math.cos(math.radians(ha)))
    cos_zen = max(-1.0, min(1.0, cos_zen))
    return 90.0 - math.degrees(math.acos(cos_zen))

def clear_sky_ghi(elevation_deg: float) -> float:
    if elevation_deg <= 0:
        return 0.0
    sin_elev = math.sin(math.radians(elevation_deg))
    # Kasten-Young air mass; simple clear-sky beam+diffuse model.
    am = 1.0 / (sin_elev + 0.50572 * (elevation_deg + 6.07995) ** -1.6364)
    ghi = 1098.0 * sin_elev * math.exp(-0.059 * am)
    return max(0.0, ghi)
