# MVBT Trail Weather

![fetch-conditions](https://github.com/ABIV/mca-practice-app/actions/workflows/fetch.yml/badge.svg)

A go/no-go dashboard for Minnesota Valley Blaze Trail (MVBT) practice venues.
A scheduled GitHub Actions job pulls live weather, air-quality, and forecast
data every 15 minutes, computes WBGT (heat stress) and applies the
**MCA-2025 Weather Policy** for each venue, and publishes the result as a
static `conditions.json`. A plain HTML/JS page reads that file and renders
current conditions, a 12-hour outlook, and a per-venue GO / CAUTION /
CANCELLED status — no server required.

## How it works

- **Pipeline (`pipeline/`, server-side, Python):** for each venue in
  `venues.json`, fetches current METAR observations, Open-Meteo HRRR model
  data (solar radiation + cloud cover), the NWS hourly forecast, NWS severe
  weather alerts, AirNow current + forecast AQI, and PurpleAir
  (Barkjohn-corrected) AQI. It computes WBGT (current conditions and a
  12-hour outlook, flagging cloud-cover mismatches as "suspect"), applies
  the MCA-2025 heat/AQI thresholds plus a stricter MVBT combined-stress
  rule, and writes `conditions.json`. Each venue's fetch is isolated — a
  failure in one source for one venue never blocks the rest; failed sources
  degrade to `UNKNOWN` with the reason recorded, never a silent fallback
  value.
- **Frontend (`index.html`, `app.js`, `styles.css`, browser):** fetches
  `conditions.json` and renders it — no computation happens client-side. It
  shows the scheduled practice's venue by default, a full venue board
  (sortable worst-first or A–Z, expandable for details), and a staleness
  warning if the data is more than 45 minutes old.
- **Publishing:** the pipeline output is committed to a separate `data`
  branch by the workflow; `main` holds only code. The page fetches
  conditions from `data` via `raw.githubusercontent.com`, so Pages (serving
  `main`) and the data feed (living on `data`) update independently.

## First-time setup

### 1. Add secrets

Go to the repo → **Settings → Secrets and variables → Actions** and add two
repository secrets:

- `AIRNOW_KEY` — an [AirNow API](https://docs.airnowapi.org/) key
- `PURPLEAIR_KEY` — a [PurpleAir API](https://api.purpleair.com/) read key

### 2. Run the first data fetch

Go to **Actions → fetch-conditions → Run workflow** and trigger it manually.
This runs `pipeline.build` and pushes `conditions.json` to a new `data`
branch (created on first run). After this, the workflow also runs on its
own every 15 minutes via the `schedule` trigger in
`.github/workflows/fetch.yml`.

### 3. Enable GitHub Pages

Go to **Settings → Pages** and set **Source = Deploy from a branch**,
**Branch = `main` / (root)**. The static page itself lives on `main`; it
reads live data from the `data` branch at request time via
`raw.githubusercontent.com`, so you don't need to (and shouldn't) deploy the
`data` branch.

## Adding a venue

Append one object to `venues.json` on `main` — nothing else needs to
change:

```json
{
  "id": "unique-slug",
  "name": "Full Venue Name",
  "short": "Short Name",
  "city": "City, ST",
  "lat": 45.000,
  "lon": -93.000,
  "metar": "KXXX",
  "notes": ""
}
```

`metar` must be the ICAO code of the nearest METAR-reporting station. The
next scheduled (or manually triggered) `fetch-conditions` run will pick up
the new venue automatically.

## Local development

```bash
python -m venv .venv
.venv/bin/pip install -r requirements.txt

# run the test suite
.venv/bin/python -m pytest

# build conditions.json locally (needs real API keys)
AIRNOW_KEY=... PURPLEAIR_KEY=... .venv/bin/python -m pipeline.build
```

To preview the frontend:

- **Open `index.html` directly (`file://`)** — it loads the bundled
  `sample-conditions.json` fixture, so you can see the UI without any keys
  or network access.
- **Serve it over HTTP** (`python -m http.server`, then visit
  `http://localhost:8000`) — it fetches live data from the `data` branch on
  GitHub instead of the sample file.

## Repository layout

```
pipeline/            data pipeline (fetch, WBGT, policy, assembly)
  sources/            one module per external data source
  build.py            orchestrator — builds conditions.json
  wbgt.py, solar.py    WBGT calculation + solar geometry
  policy.py           MCA-2025 ruleset + combined-stress rule
  models.py           Signal/VenueConditions data contract
tests/                pytest suite (unit + fixture-based)
.github/workflows/    fetch-conditions scheduled workflow
venues.json           venue list (edit this to add/remove venues)
sample-conditions.json  fixture used by the frontend on file://
index.html, app.js, styles.css  static frontend, reads conditions.json
```

## Data sources

| Source | Used for |
|---|---|
| METAR | Current temp, RH, wind at the nearest station |
| Open-Meteo HRRR | Solar radiation (GHI) + cloud cover, current and 12h outlook |
| NWS hourly forecast | Forecast temp/wind, storm/severe flags |
| NWS alerts | Active severe-weather warnings (auto-cancel triggers) |
| AirNow | Current AQI (authoritative) + forecast AQI |
| PurpleAir | Corrected (Barkjohn) AQI as a secondary/cross-check reading |

## Reading the dashboard

Every value in `conditions.json` carries provenance (source, station,
distance, fetch time) and a status of `ok`, `unknown`, or `suspect`. A
value of `UNKNOWN` means a source failed and the app is explicitly telling
you it doesn't know — it never silently substitutes a guess. Trust the
policy as a floor, not a ceiling: the footer's reminder applies — *"Your
senses supersede this app. If you hear thunder, clear the trail."*
