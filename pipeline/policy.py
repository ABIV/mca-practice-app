"""MCA Weather Policy 2025, implemented verbatim as a versioned ruleset.
Source: minnesotacycling.org/wp-content/uploads/2025/07/MCA-Weather-Policy-2025-.pdf (2025)

Plus the MVBT-local combined-stress rule (stricter than MCA).
"""
from pipeline.models import GO, CAUTION, CANCELLED, UNKNOWN

RULESET_VERSION = "MCA-2025"
_ORDER = {GO: 0, CAUTION: 1, UNKNOWN: 2, CANCELLED: 3}

def _worse(a, b):
    return a if _ORDER[a] >= _ORDER[b] else b

def _heat(wbgt):
    if wbgt < 82.0:
        return GO, None
    if wbgt <= 85.0:
        return CAUTION, "Heat WBGT 82-85F: 2-hour max activity, decrease intensity/duration, provide rest breaks"
    if wbgt <= 87.1:
        return CAUTION, "Heat WBGT 85.1-87.1F: 1-hour max activity, significantly increase rest breaks"
    return CANCELLED, "Heat WBGT >87.1F: practice cancelled"

def _air(aqi):
    if aqi <= 50:
        return GO, None
    if aqi <= 100:
        return GO, "AQI Yellow (51-100): check in with air-quality-sensitive athletes; consider reduced duration/intensity for sensitive groups"
    if aqi <= 150:
        return CAUTION, "AQI Orange (101-150): asthmatic athletes indoors; competitive activities cancelled; others reduced duration/intensity"
    return CANCELLED, "AQI Red (>150): practice cancelled"

def _escalate(status):
    if status == GO:
        return CAUTION
    if status == CAUTION:
        return CANCELLED
    return status

def evaluate(signals: dict) -> dict:
    reasons = []
    status = GO

    # Safety-critical UNKNOWN capping
    unknown = ((not signals.get("wbgt_known", False)) or (not signals.get("aqi_known", False))
               or (not signals.get("alerts_known", True)))

    if signals.get("wbgt_known") and signals.get("wbgt") is not None:
        hs, hr = _heat(signals["wbgt"])
        status = _worse(status, hs)
        if hr:
            reasons.append({"rule": "heat", "detail": hr})

    if signals.get("aqi_known") and signals.get("aqi") is not None:
        as_, ar = _air(signals["aqi"])
        status = _worse(status, as_)
        if ar:
            reasons.append({"rule": "air_quality", "detail": ar})

    for w in signals.get("severe_warnings", []):
        if any(k in w for k in ("Severe Thunderstorm Warning", "Tornado Warning", "Flash Flood Warning")):
            status = _worse(status, CANCELLED)
            reasons.append({"rule": "severe_weather", "detail": f"{w}: practice cancelled"})

    if signals.get("storm_forecast"):
        status = _worse(status, CAUTION)
        reasons.append({"rule": "storm_forecast",
                        "detail": "Storms forecast — lightning within 10 mi cancels; if you hear thunder, clear the trail; wait 30 min after last thunder/lightning"})

    # MVBT local combined-stress (only when both signals known)
    if (signals.get("aqi_known") and signals.get("wbgt_known")
            and signals.get("aqi") is not None and signals.get("wbgt") is not None
            and signals["aqi"] > 100 and signals["wbgt"] > 80.0):
        status = _escalate(status)
        reasons.append({"rule": "mvbt_combined_stress",
                        "detail": "MVBT — stricter than MCA policy: AQI>100 and WBGT>80 simultaneously → escalated one level (combined heat + smoke stress)"})

    if unknown:
        status = _worse(status, UNKNOWN)
        missing = []
        if not signals.get("wbgt_known"):
            missing.append("WBGT")
        if not signals.get("aqi_known"):
            missing.append("current AQI")
        if not signals.get("alerts_known", True):
            missing.append("severe-weather alerts")
        reasons.append({"rule": "unknown",
                        "detail": f"Missing safety-critical signal(s): {', '.join(missing)} — status capped at UNKNOWN"})

    return {"status": status, "reasons": reasons}
