"""WBGT (Wet Bulb Globe Temperature), NWS/Dimiceli-style, all outputs in F.

- Psychrometric wet bulb: Stull (2011).
- Black globe: 150 mm globe, emissivity 0.95; Newton iteration on the
  convective-radiative energy balance (Ranz-Marshall Nusselt for a sphere).
- Natural wet bulb: psychrometric wet bulb plus a solar/wind correction.
- WBGT = 0.7*Tnwb + 0.2*Tg + 0.1*Tdb.

Validated against: Stull 20C/50%->13.7C; hot/dry 89F/33%/9.6mph/462 -> ~76-78F.
Tuned constants (final): _NU_C = 0.6, _NWB_SOLAR = 0.0135.
If a reference test misses, tune the convective constant `_NU_C` (globe) and the
natural-wet-bulb solar coefficient `_NWB_SOLAR`; do NOT change the WBGT weights.
"""
import math

SIGMA = 5.670374419e-8      # Stefan-Boltzmann, W/m^2/K^4
GLOBE_D = 0.15              # globe diameter, m
GLOBE_EMISS = 0.95
GLOBE_ABSORB = 0.95
K_AIR = 0.026              # air thermal conductivity, W/m/K
NU_AIR = 1.5e-5            # air kinematic viscosity, m^2/s
PR_AIR = 0.71
_NU_C = 0.6                # Ranz-Marshall coefficient
_NWB_SOLAR = 0.0135        # natural wet bulb solar loading coefficient (F per W/m^2, scaled)

def _f_to_c(f): return (f - 32.0) * 5.0 / 9.0
def _c_to_f(c): return c * 9.0 / 5.0 + 32.0
def _mph_to_ms(v): return v * 0.44704

def stull_wet_bulb_c(temp_c: float, rh_pct: float) -> float:
    rh = max(1.0, min(100.0, rh_pct))
    t = temp_c
    return (t * math.atan(0.151977 * (rh + 8.313659) ** 0.5)
            + math.atan(t + rh) - math.atan(rh - 1.676331)
            + 0.00391838 * rh ** 1.5 * math.atan(0.023101 * rh)
            - 4.686035)

def black_globe_f(temp_f: float, wind_mph: float, ghi_wm2: float) -> float:
    ta = _f_to_c(temp_f) + 273.15  # K
    v = max(0.1, _mph_to_ms(wind_mph))
    re = v * GLOBE_D / NU_AIR
    nu = 2.0 + _NU_C * re ** 0.5 * PR_AIR ** (1.0 / 3.0)
    h = nu * K_AIR / GLOBE_D  # convective coefficient, W/m^2/K
    q_solar = GLOBE_ABSORB * ghi_wm2 / 4.0  # sphere projected/surface area = 1/4

    def f(tg):
        return (GLOBE_EMISS * SIGMA * tg ** 4 + h * (tg - ta)
                - GLOBE_EMISS * SIGMA * ta ** 4 - q_solar)

    def fprime(tg):
        return 4 * GLOBE_EMISS * SIGMA * tg ** 3 + h

    tg = ta + 5.0
    for _ in range(50):
        step = f(tg) / fprime(tg)
        tg -= step
        if abs(step) < 1e-4:
            break
    return _c_to_f(tg - 273.15)

def natural_wet_bulb_f(temp_f: float, rh_pct: float, wind_mph: float, ghi_wm2: float) -> float:
    twb_c = stull_wet_bulb_c(_f_to_c(temp_f), rh_pct)
    twb_f = _c_to_f(twb_c)
    # Solar loading raises natural wet bulb; wind reduces it.
    solar_term = _NWB_SOLAR * ghi_wm2 / (1.0 + 0.5 * max(0.0, wind_mph))
    return twb_f + solar_term

def wbgt_f(temp_f: float, rh_pct: float, wind_mph: float, ghi_wm2: float) -> float:
    tnwb = natural_wet_bulb_f(temp_f, rh_pct, wind_mph, ghi_wm2)
    tg = black_globe_f(temp_f, wind_mph, ghi_wm2)
    return 0.7 * tnwb + 0.2 * tg + 0.1 * temp_f
