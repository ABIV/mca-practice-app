"""US EPA PM2.5 -> AQI (breakpoints effective 2024-05-06) and the
Barkjohn (2021) US-wide correction for raw PurpleAir pm2.5_cf_1.

NOTE: rows above AQI 150 are display-only; policy CANCELS above 150 regardless,
so exact upper-hazardous breakpoints do not affect status decisions.
"""
import math

# (C_low, C_high, I_low, I_high) — PM2.5 24h, EPA 2024
_BP = [
    (0.0,   9.0,   0,   50),
    (9.1,   35.4,  51,  100),
    (35.5,  55.4,  101, 150),
    (55.5,  125.4, 151, 200),
    (125.5, 225.4, 201, 300),
    (225.5, 325.4, 301, 500),  # display-only upper bound
]

def pm25_to_aqi(pm25: float) -> int:
    c = max(0.0, math.floor(pm25 * 10) / 10.0)  # truncate to 0.1 per EPA
    for c_low, c_high, i_low, i_high in _BP:
        if c <= c_high:
            return round((i_high - i_low) / (c_high - c_low) * (c - c_low) + i_low)
    return 500

def barkjohn_correct(pa_cf1: float, humidity_pct: float) -> float:
    pa = max(0.0, pa_cf1)
    rh = humidity_pct
    if pa <= 343.0:
        corrected = 0.52 * pa - 0.086 * rh + 5.75
    else:
        corrected = 0.46 * pa + 3.93e-4 * pa ** 2 + 2.97
    return max(0.0, corrected)
