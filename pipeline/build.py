"""Orchestrator: per-venue fetch (isolated), WBGT + policy, assemble conditions.json."""
import os, json, datetime
from zoneinfo import ZoneInfo
from pipeline import http, wbgt, solar, policy, models, units
from pipeline.models import Signal, HourPoint, VenueConditions, UNKNOWN
from pipeline.sources import metar, openmeteo, nws_forecast, nws_alerts, airnow, purpleair, schedule

CENTRAL = ZoneInfo("America/Chicago")

def _try(fn, source_name):
    try:
        return fn(), None
    except http.SourceError as e:
        return None, Signal.unknown(f"{source_name}: {e}", source=source_name)

def _wbgt_for(temp_f, rh, wind, ghi, cloud, elevation):
    """Return (wbgt_f, wbgt_suspect_or_None)."""
    val = wbgt.wbgt_f(temp_f, rh, wind, ghi)
    suspect = None
    csky = solar.clear_sky_ghi(elevation)
    if cloud is not None and cloud > 80 and csky > 0 and ghi > 0.6 * csky:
        reduced = min(ghi, 0.25 * csky)  # cloud-reduced estimate
        suspect = wbgt.wbgt_f(temp_f, rh, wind, reduced)
    return round(val, 1), (round(suspect, 1) if suspect is not None else None)

_OM_UNSET = object()

def build_venue(venue, keys, now, schedule_events, om=_OM_UNSET):
    vc = VenueConditions(venue_id=venue["id"], name=venue["name"])
    lat, lon = venue["lat"], venue["lon"]

    cur_metar, m_unknown = _try(lambda: metar.fetch_current(venue["metar"]), "METAR")
    # om is normally pre-fetched by build_all's one batched call and passed in
    # (None if that venue's slice failed). When not provided (direct/unit call),
    # fetch this venue's own.
    if om is _OM_UNSET:
        om, _ = _try(lambda: openmeteo.fetch(lat, lon), "Open-Meteo HRRR")
    fc, fc_unknown = _try(lambda: nws_forecast.fetch(lat, lon), "NWS forecast")
    al, _ = _try(lambda: nws_alerts.fetch(lat, lon), "NWS alerts")
    alerts_known = al is not None
    an, an_unknown = _try(lambda: airnow.fetch_current(lat, lon, keys["airnow"]), "AirNow")
    anf, _ = _try(lambda: airnow.fetch_forecast(lat, lon, keys["airnow"]), "AirNow forecast")
    pa, _ = _try(lambda: purpleair.fetch_nearest(lat, lon, keys["purpleair"]), "PurpleAir")

    alerts = al or {"cancel": [], "flags": []}
    vc.alerts = alerts.get("cancel", [])
    vc.flags = alerts.get("flags", [])
    if not alerts_known:
        vc.flags.append("⚠️ Severe-weather alert check failed — verify manually before practice")
    if fc is None:
        vc.flags.append("⚠️ NWS hourly forecast unavailable — forecast temp/wind from HRRR model; storm flags unavailable")

    # ---- current WBGT ----
    cur_wbgt = None
    cur_wbgt_known = False
    cur_suspect = None
    if cur_metar and om and om["hours"]:
        h0 = om["hours"][0]
        elev = solar.solar_elevation_deg(now.astimezone(ZoneInfo("UTC")), lat, lon)
        ghi = h0.get("ghi") or 0.0
        cur_wbgt, cur_suspect = _wbgt_for(cur_metar["temp_f"], cur_metar["rh_pct"],
                                          cur_metar["wind_mph"], ghi, h0.get("cloud_pct"), elev)
        cur_wbgt_known = True
    # current AQI (AirNow authoritative)
    cur_aqi = an["aqi"] if an else None
    cur_aqi_known = an is not None

    # ---- current-conditions provenance block ----
    vc.current = {
        "temp": (Signal(cur_metar["temp_f"], "ok", "METAR", cur_metar["station"], None, cur_metar["fetched_at"]).to_dict()
                 if cur_metar else Signal.unknown("METAR failed", "METAR").to_dict()),
        "rh": (Signal(cur_metar["rh_pct"], "ok", "METAR", cur_metar["station"], None, cur_metar["fetched_at"]).to_dict()
               if cur_metar else Signal.unknown("METAR failed", "METAR").to_dict()),
        "wind": (Signal(cur_metar["wind_mph"], "ok", "METAR", cur_metar["station"], None, cur_metar["fetched_at"]).to_dict()
                 if cur_metar else Signal.unknown("METAR failed", "METAR").to_dict()),
        "ghi": (Signal(om["hours"][0].get("ghi"), "ok", "Open-Meteo HRRR", None, None, om["fetched_at"]).to_dict()
                if om else Signal.unknown("Open-Meteo HRRR unavailable", "Open-Meteo HRRR").to_dict()),
        "wbgt": (Signal(cur_wbgt, "ok", "computed",
                        extra=({"wbgt_suspect": cur_suspect} if cur_suspect is not None else {})).to_dict()
                 if cur_wbgt_known
                 else Signal.unknown("WBGT inputs missing", "computed").to_dict()),
        "aqi": (Signal(an["aqi"], "ok", "AirNow", an["reporting_area"], an["distance_mi"], an["fetched_at"],
                       extra={"pollutant": an["pollutant"], "category": an["category"]}).to_dict()
                if an else Signal.unknown("AirNow failed", "AirNow").to_dict()),
        "aqi_purpleair": (Signal(pa["aqi"], "ok", "PurpleAir (EPA-corrected)", f"sensor {pa['sensor_index']}",
                                 pa["distance_mi"], pa["fetched_at"], extra={"pm25_corrected": pa["pm25_corrected"]}).to_dict()
                          if pa else Signal.unknown("PurpleAir failed", "PurpleAir").to_dict()),
        "aqi_forecast": (Signal(anf["aqi"], "ok", "AirNow forecast", None, None, anf["fetched_at"],
                                extra={"label": "forecast — verify with current reading"}).to_dict()
                         if anf and anf.get("aqi") is not None
                         else Signal.unknown("no AirNow forecast", "AirNow forecast").to_dict()),
    }

    # AQI disagreement flag
    if an and pa and abs(an["aqi"] - pa["aqi"]) >= 50:
        vc.flags.append(f"AQI disagreement: AirNow {an['aqi']} vs PurpleAir {pa['aqi']} (corrected) — verify")

    # ---- current status ----
    cur_eval = policy.evaluate({
        "wbgt": cur_wbgt, "wbgt_known": cur_wbgt_known,
        "aqi": cur_aqi, "aqi_known": cur_aqi_known,
        "alerts_known": alerts_known,
        "severe_warnings": alerts.get("cancel", []),
        "storm_forecast": False,
    })
    vc.status = cur_eval["status"]
    vc.reasons = cur_eval["reasons"]

    # ---- forecast hours ----
    # NOTE: Open-Meteo and NWS format time_iso differently ("2026-07-20T11:00"
    # vs "2026-07-20T11:00:00-05:00" for the same local Central hour), so we
    # match on the "YYYY-MM-DDTHH" hour prefix rather than exact string
    # equality — otherwise the NWS hour (the intended temp/RH/wind driver,
    # and the source of storm_forecast) would never be found.
    fc_hours = {h["time_iso"][:13]: h for h in (fc["hours"] if fc else [])}
    hours_out = []
    if om:
        for i, omh in enumerate(om["hours"][1:13]):
            t_iso = omh["time_iso"]
            utc = datetime.datetime.fromisoformat(t_iso).replace(tzinfo=CENTRAL).astimezone(ZoneInfo("UTC"))
            elev = solar.solar_elevation_deg(utc, lat, lon)
            # temp/RH/wind from NWS (driver); fall back to HRRR only if NWS hour missing
            nwsh = fc_hours.get(t_iso[:13])
            temp = (nwsh or omh).get("temp_f")
            rh = (nwsh or omh).get("rh_pct")
            wind = (nwsh or omh).get("wind_mph")
            ghi = omh.get("ghi") or 0.0
            known = temp is not None and rh is not None and wind is not None
            wv, ws = (_wbgt_for(temp, rh, wind, ghi, omh.get("cloud_pct"), elev) if known else (None, None))
            is_storm = bool(nwsh and nwsh.get("is_storm"))
            ev = policy.evaluate({
                "wbgt": wv, "wbgt_known": known,
                "aqi": cur_aqi, "aqi_known": cur_aqi_known,   # current AQI applies; forecast AQI never drives
                "alerts_known": alerts_known,
                "severe_warnings": alerts.get("cancel", []),
                "storm_forecast": is_storm,
            })
            hours_out.append(HourPoint(
                time_iso=t_iso, wbgt_f=wv, wbgt_suspect=ws,
                aqi_forecast=(anf.get("aqi") if anf else None),
                precip_pct=(nwsh or omh).get("precip_pct"),
                weather_code=(nwsh.get("short") if nwsh else str(omh.get("weather_code"))),
                status=ev["status"], reasons=ev["reasons"]).to_dict())
    elif fc:
        for nwsh in fc["hours"][:12]:
            ev = policy.evaluate({"wbgt": None, "wbgt_known": False,
                                  "aqi": cur_aqi, "aqi_known": cur_aqi_known,
                                  "alerts_known": alerts_known,
                                  "severe_warnings": alerts.get("cancel", []),
                                  "storm_forecast": bool(nwsh.get("is_storm"))})
            hours_out.append(HourPoint(time_iso=nwsh["time_iso"], wbgt_f=None,
                                       aqi_forecast=(anf.get("aqi") if anf else None),
                                       precip_pct=nwsh.get("precip_pct"),
                                       weather_code=nwsh.get("short"),
                                       status=ev["status"], reasons=ev["reasons"]).to_dict())
    # if both om and fc are None, hours_out stays [] (current status already UNKNOWN)
    vc.hours = hours_out

    # ---- practice hour ----
    practice = next((e for e in schedule_events if e.get("venue_id") == venue["id"]), None)
    if practice:
        vc.practice_hour_iso = practice["start_iso"]
        target = practice["start_iso"][:13]  # match to the hour
        ph = next((h for h in hours_out if h["time_iso"][:13] == target), None)
        if ph:
            vc.practice_status = ph["status"]
            vc.practice_reasons = ph["reasons"]
    return vc.to_dict()

def build_all(venues, keys, now=None):
    now = now or datetime.datetime.now(CENTRAL)
    events = []
    try:
        events = schedule.fetch_today(venues, now=now)
    except http.SourceError:
        events = []
    # One batched Open-Meteo call for all venues, instead of one per venue — the
    # per-venue volume was rate-limiting the shared CI runner IP. Per-venue
    # isolation is preserved: fetch_many aligns results to input order with a
    # latitude identity guard, and each venue receives only its own slice.
    try:
        om_list = openmeteo.fetch_many([(v["lat"], v["lon"]) for v in venues])
    except http.SourceError:
        om_list = [None] * len(venues)
    return {
        "generated_at": now.isoformat(timespec="seconds"),
        "ruleset": policy.RULESET_VERSION,
        "schedule": events,
        "venues": [build_venue(v, keys, now, events, om=om_list[i]) for i, v in enumerate(venues)],
    }

def main():
    keys = {"airnow": os.environ["AIRNOW_KEY"], "purpleair": os.environ["PURPLEAIR_KEY"]}
    venues = json.loads(open("venues.json").read())
    out = build_all(venues, keys)
    with open("conditions.json", "w") as f:
        json.dump(out, f, indent=2)
    print(f"wrote conditions.json: {len(out['venues'])} venues at {out['generated_at']}")

if __name__ == "__main__":
    main()
