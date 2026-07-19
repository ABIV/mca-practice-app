# MVBT Trail Weather — Practice Go/No-Go Dashboard

**Date:** 2026-07-19
**Status:** Design approved, pending spec review
**Target repo:** `ABIV/mca-practice-app` (replaces existing contents)
**Local working dir:** `/Users/arthurbeisang/Development/MCA Weather Widget`

## Purpose

A static web app + GitHub Actions data pipeline that tells Mounds View Bike Team (MVBT)
coaches whether practice is safe at the scheduled venue, and shows conditions across all
venues so a coach can pick a substitute a few hours ahead. Replaces a commercial app
(Zelus, ~$300/user/yr). Coaches check it on phones at trailheads; the go/cancel decision
must be makeable in under 30 seconds.

**Accuracy is the point of this project.** The app it replaces made two dangerous errors we
are explicitly designing against: (1) it reused one venue's data for another, and (2) it
silently defaulted AQI to 35 during a hazardous smoke event. Neither is permitted here.

## Non-negotiable rules (design constraints)

1. **Per-venue isolation.** Every venue fetches its own data inside the loop. Never reuse
   one venue's data for another.
2. **No silent fallbacks.** A failed fetch produces `"status": "unknown"` for that signal,
   rendered as ⚠️ UNKNOWN. Never default a value (especially AQI) to a number.
3. **Provenance on every value.** Every value in `conditions.json` carries `source`,
   `station_or_monitor`, `distance_mi` (where applicable), and `fetched_at` (ISO, Central).
4. **UNKNOWN caps status.** UNKNOWN on any safety-critical signal (current AQI, current or
   practice-hour WBGT) caps overall status at UNKNOWN — never GO.
5. **Forecast AQI is planning-grade only.** Open-Meteo `us_aqi` is labeled everywhere as
   "model forecast — verify with current reading" and never drives a green status on its own.
   (It missed a wildfire smoke event, reporting PM2.5 ~7 µg/m³ during an AQI-187 day.)
6. **Rate limits.** Single project-identifying User-Agent; well under AirNow's 500/hr even
   with ~15 venues at a 15-minute cadence.

## Architecture

**Core decision: all weather logic runs in Python inside the cron; the browser is a pure
renderer.** WBGT, the solar model, and the policy engine execute server-side and bake their
results into `conditions.json`. No policy or WBGT math runs in JavaScript, ever.

Rationale: one authoritative, unit-tested implementation; the smoke-event regression fixture
exercises the real code path; the phone client stays tiny and fast on LTE; no JS/Python
policy drift.

To keep venue-override and practice-hour interactivity working against baked results, the
cron computes — **for every venue** — a status + reasons for *current* conditions **and** for
*each of the next 12 forecast hours*. Client interactions ("scheduled at Wolly, actually
riding Elm Creek at 5pm") become a lookup, not a recompute.

### Repository & branch layout

```
main branch (clean source)              data branch (cron output only)
├── index.html                          └── conditions.json   ← committed every 15 min
├── app.js            (render only, vanilla ES modules)
├── styles.css
├── venues.json       (hand-maintained; the only config)
├── pipeline/
│   ├── build.py      (orchestrator: loop venues, no cross-contamination)
│   ├── wbgt.py       (pure: Dimiceli/NWS WBGT, Newton-iteration black globe)
│   ├── solar.py      (pure: true solar time, elevation, clear-sky GHI max)
│   ├── policy.py     (pure: MCA-2025 versioned ruleset)
│   ├── sources/
│   │   ├── metar.py          (api.weather.gov station latest obs)
│   │   ├── nws_forecast.py   (points -> forecastHourly, 12h)
│   │   ├── nws_alerts.py     (alerts/active?point=)
│   │   ├── airnow.py         (AirNow current obs by lat/long)
│   │   ├── openmeteo.py      (shortwave_radiation + us_aqi hourly)
│   │   └── schedule.py       (TeamSnap iCal parse -> today's events)
│   ├── models.py     (venue + signal + conditions dataclasses)
│   └── tests/        (pytest)
├── requirements.txt
└── .github/workflows/fetch.yml   (*/15 cron + workflow_dispatch)
```

**Data delivery.** GitHub Pages serves the site from `main` (root). The page fetches
`conditions.json` from the `data` branch via
`https://raw.githubusercontent.com/ABIV/mca-practice-app/data/conditions.json`, cache-busted
with `?t={epoch}`. Verified: raw.githubusercontent.com returns `access-control-allow-origin: *`
with a 5-minute CDN cache — acceptable for a 15-minute cron and keeps `main` free of data
churn. No per-update deploy step.

**Workflow writes to the data branch.** `fetch.yml` checks out the `data` branch (creating it
orphaned on first run), runs `python -m pipeline.build`, writes `conditions.json`, commits and
pushes to `data` only. Job failure surfaces in the Actions badge.

## Data pipeline (per cron run)

`build.py` loops venues from `venues.json`. Each venue fetches its own data inside the loop.
Per signal, on any failure → that signal's `status` is `"unknown"` (no fallback number).

Per venue, each run fetches:

1. **Current weather (METAR):** latest obs from
   `api.weather.gov/stations/{metar}/observations/latest` → temp, RH, wind.
2. **Solar (current hour):** Open-Meteo `shortwave_radiation` (GHI, W/m²). **Sanity check:**
   if `cloud_cover > 80%` AND `GHI > 60%` of the clear-sky max for the current sun elevation,
   flag solar as *suspect* and compute WBGT **both ways** (measured GHI and a cloud-reduced
   GHI); include both in output.
3. **Forecast weather:** `api.weather.gov/points/{lat},{lon}` → `forecastHourly`, next 12 hours
   (temp, RH, wind, precip probability, short forecast / weather codes).
4. **Current AQI (authoritative):** AirNow
   `airnowapi.org/aq/observation/latLong/current` (key in repo secret `AIRNOW_KEY`). Records
   reporting area, approximate monitor distance, and the **dominant pollutant** (PM2.5 vs O3).
5. **Forecast AQI (planning-grade):** Open-Meteo air-quality `us_aqi` hourly. Labeled model
   forecast; never drives green.
6. **NWS active alerts:** `api.weather.gov/alerts/active?point={lat},{lon}`. Severe
   Thunderstorm / Tornado / Flash Flood **Warning** → CANCEL. Watches and Air Quality Alerts →
   shown as flags.
7. **Schedule:** TeamSnap iCal
   (`http://ical-cdn.teamsnap.com/team_schedule/085d0f1e-1abe-42ca-999e-ef79981f7bba.ics`,
   cache-busted) parsed server-side. Today's events (title, location, start/end) embedded in
   `conditions.json`, each matched to a venue by substring against name/short/city (unmatched →
   flagged for the client to prompt a pick). Parsing server-side avoids a CORS proxy.

Every emitted value carries `source`, `station_or_monitor`, `distance_mi` (where applicable),
`fetched_at` (ISO, America/Chicago). A top-level `generated_at` timestamp drives the client
staleness warning.

## WBGT calculation (`wbgt.py`)

Dimiceli/NWS-style WBGT from (temp °F, RH %, wind mph, GHI W/m², solar elevation):

- Psychrometric wet bulb via **Stull**, then natural wet bulb correction for solar/wind.
- Black globe via **iterative radiative/convective energy balance** (Newton iteration, not a
  linear fudge).
- Solar elevation uses **true solar time** (longitude correction + equation of time), not
  clock hour (`solar.py`).
- **Do NOT clamp** measured/forecast GHI to a clear-sky floor — use the provided GHI; it
  already reflects clouds. (The clear-sky max is used only for the step-2 suspect check.)
- `WBGT = 0.7·Tnwb + 0.2·Tg + 0.1·Tdb`.
- Computed for current obs **and** each of the 12 forecast hours.

Unit-tested against NWS WBGT calculator references, a hot/dry case
(89°F, 33% RH, 9.6 mph, 462 W/m² → expect ≈76–78°F), and a humid case.

## Policy engine (`policy.py`, versioned "MCA-2025")

Pure module. `evaluate(signals) → {status: GO|CAUTION|CANCELLED|UNKNOWN, reasons: [{rule, detail}]}`.
Implements the MCA Weather Policy 2025 verbatim. Docstring stamps the source URL
(`minnesotacycling.org/wp-content/uploads/2025/07/MCA-Weather-Policy-2025-.pdf`) and "2025".

**Heat (WBGT °F):**
- `< 82` → normal
- `82–85` → CAUTION: "2-hour maximum activity, decrease intensity/duration, provide rest breaks"
- `85.1–87.1` → CAUTION: "1-hour maximum activity, significantly increase rest breaks"
- `> 87.1` → CANCELLED

**Air quality (AQI):**
- `0–50` (green) → normal
- `51–100` (yellow) → note: "check in with athletes with air-quality sensitivities; consider
  reduced duration/intensity for sensitive groups"
- `101–150` (orange) → CAUTION: "athletes with asthma move indoors; competitive activities
  cancelled; all others reduced duration/intensity"
- `> 150` → CANCELLED

**Severe weather:** NWS Severe Thunderstorm / Tornado / Flash Flood **Warning** at the venue →
CANCELLED. Thunderstorm weather codes in the forecast for the practice hour → CAUTION flag
("storms forecast — lightning within 10 mi cancels; if you hear thunder, clear the trail;
wait 30 min after last thunder/lightning").

**Local rule (label "MVBT — stricter than MCA policy"):** `AQI > 100` AND `WBGT > 80`
simultaneously → escalate one level (combined heat + smoke stress).

**Aggregation:** overall status = worst of all signals. UNKNOWN on any safety-critical signal
(current AQI, current or practice-hour WBGT) caps status at UNKNOWN, never GO.

**Practice-hour status** specifically = forecast WBGT at that hour + current AirNow AQI +
active severe alerts + storm-code flag. Forecast AQI never folds into status.

Designed as a versioned ruleset so future policy years bolt on without rewriting callers.

## UI (single page, mobile-first)

High-contrast, sunlight-readable. Status colors green / yellow / red / gray. No login. Loads
fast on LTE. Renders only; all statuses/reasons come pre-computed from `conditions.json`.

**Section 1 — Scheduled practice.** Uses today's schedule embedded in the JSON. Matches
today's event to a venue; unmatched → prompt to pick. Manual **venue override dropdown**
("scheduled at Wolly, actually riding Elm Creek"). Shows: big **status chip** with primary
reason, the **evaluated practice hour** clearly labeled, a **current-conditions row**, and a
**12-hour strip** (compact table/sparkline of WBGT + AQI + precip) so a coach can see if
later/tomorrow clears.

**Section 2 — System board.** One row per venue: name, current status chip, current WBGT,
current AQI (+ dominant pollutant + monitor distance), status at the practice hour, alert
flags. Sort **worst-first**, toggle to alphabetical. **Tap to expand:** hourly strip + raw
inputs (temp/RH/wind/solar/source/timestamps) — coaches trust numbers they can inspect.

**Footer (always visible):** "Your senses supersede this app. If you hear thunder, clear the
trail." + data timestamp + **staleness warning if data > 45 min old** + link to the MCA policy
PDF.

## venues.json (seed)

Hand-maintained; the only config. Adding a venue requires **nothing but a JSON entry**.
Seeded with two, **coordinates and nearest METAR to be verified during the build** (current
values approximate):

```json
[
  {"id": "wolly", "name": "Woolly Trails", "short": "Wolly",
   "city": "St. Croix Falls, WI", "lat": 45.395, "lon": -92.635,
   "metar": "KOEO", "notes": ""},
  {"id": "elm-creek", "name": "Elm Creek Park Reserve", "short": "Elm Creek",
   "city": "Maple Grove, MN", "lat": 45.176, "lon": -93.430,
   "metar": "KMIC", "notes": ""}
]
```

Venue model is a plain record so more venues (and later, per-venue metadata) bolt on cleanly.

## Testing / done criteria

**pytest unit tests:**
- WBGT reference values: NWS calculator examples, the hot/dry case (89°F/33%/9.6mph/462 W/m²
  → ≈76–78°F), and a humid case.
- Every policy band boundary: WBGT 81.9 / 82.0 / 85.0 / 85.1 / 87.1 / 87.2; AQI 50 / 51 / 100
  / 101 / 150 / 151.
- UNKNOWN propagation (safety-critical signal missing → status capped at UNKNOWN).
- The combined-stress local rule (AQI>100 AND WBGT>80 escalates one level).

**Regression fixture — 2026-07-19 smoke event:** AirNow-style AQI 187 at Wolly must produce
CANCELLED with reason "AQI Red (>150)", and a simulated Open-Meteo AQI of 76 for the same hour
must be shown only as labeled forecast, not override status.

**Workflow:** runs on cron (`*/15 * * * *`) and on `workflow_dispatch`; failures visible in the
badge; page shows a staleness warning if data > 45 min old.

**Done when:** the user opens the page on a phone, sees the scheduled venue's call with reasons
and sources, scans all venues, and can make the move/cancel decision in under 30 seconds.

## Out of scope (do not build)

Notifications/push, Blitzortung strike detection, Trailbot integration, multi-team accounts,
historical logging. The venue model (records) and policy engine (versioned ruleset) are
structured so these bolt on later, but none are implemented now.

## Open items to resolve during build

- Verify seed venue coordinates and nearest METAR stations (KOEO / KMIC and the lat/lons)
  against the actual trailheads.
- Confirm AirNow's exact current-observation response shape (fields for dominant pollutant,
  reporting area, and how to derive monitor distance).
