const DATA_URL = "https://raw.githubusercontent.com/ABIV/mca-practice-app/data/conditions.json";
const ORDER = { CANCELLED: 0, UNKNOWN: 1, CAUTION: 2, GO: 3 };
let STATE = { data: null, sortWorst: true, selectedVenue: null };

async function load() {
  const local = location.protocol === "file:";
  const url = local ? "./sample-conditions.json" : `${DATA_URL}?t=${Date.now()}`;
  try {
    const r = await fetch(url, { cache: "no-store" });
    if (!r.ok) throw new Error("HTTP " + r.status);
    STATE.data = await r.json();
    render();
  } catch (e) {
    document.getElementById("scheduled-body").innerHTML =
      `<p class="chip UNKNOWN">⚠️ Could not load conditions (${e.message})</p>`;
  }
}

function chip(status, big) {
  return `<span class="chip ${status} ${big ? "big-chip" : ""}">${status}</span>`;
}
function num(v, unit = "") { return v === null || v === undefined ? "—" : `${v}${unit}`; }

function staleness(generatedAt) {
  const el = document.getElementById("staleness");
  const ageMin = (Date.now() - new Date(generatedAt).getTime()) / 60000;
  if (ageMin > 45) {
    el.hidden = false;
    el.textContent = `⚠️ Data is ${Math.round(ageMin)} min old — may be stale`;
  } else el.hidden = true;
  document.getElementById("data-time").textContent =
    `Data updated ${new Date(generatedAt).toLocaleString()}`;
}

function venueById(id) { return STATE.data.venues.find(v => v.venue_id === id); }

function renderVenuePicker() {
  const sel = document.getElementById("venue-select");
  sel.innerHTML = STATE.data.venues
    .map(v => `<option value="${v.venue_id}">${v.name}</option>`).join("");
  // default: today's scheduled matched venue, else first
  const sched = (STATE.data.schedule || []).find(e => e.venue_id);
  STATE.selectedVenue = STATE.selectedVenue || (sched && sched.venue_id) || STATE.data.venues[0].venue_id;
  sel.value = STATE.selectedVenue;
  sel.onchange = () => { STATE.selectedVenue = sel.value; renderScheduled(); };
}

// A hourly-strip cell: the value (with optional unit) or a muted placeholder
// when the reading is empty, so every row stays aligned and the gap is visible.
function cellVal(v, unit = "") {
  return (v === null || v === undefined) ? `<span class="empty">–</span>` : `${v}${unit}`;
}

// 12-hour strip as labeled rows: an icon in front of each row identifies the
// reading (🌡️ WBGT, 🌫️ AQI, 🌧️ precip); the icon column stays pinned while the
// hours scroll. WBGT is color-coded by that hour's status.
function strip(hours) {
  if (!hours.length) return `<div class="strip empty-strip">No hourly forecast</div>`;
  const cols = `grid-template-columns:1.7rem repeat(${hours.length},minmax(2.3rem,1fr));`;
  const times = hours.map(h =>
    `<span class="scell time">${new Date(h.time_iso).toLocaleTimeString([], { hour: "numeric" })}</span>`).join("");
  const wbgt = hours.map(h =>
    `<span class="scell w ${h.status}" title="WBGT — ${h.status}">${cellVal(h.wbgt_f)}</span>`).join("");
  const aqi = hours.map(h => `<span class="scell">${cellVal(h.aqi_forecast)}</span>`).join("");
  const prec = hours.map(h => `<span class="scell">${cellVal(h.precip_pct, "%")}</span>`).join("");
  return `<div class="strip">
    <div class="srow" style="${cols}"><span class="sico"></span>${times}</div>
    <div class="srow" style="${cols}"><span class="sico" title="WBGT (°F)">🌡️</span>${wbgt}</div>
    <div class="srow" style="${cols}"><span class="sico" title="Air Quality Index">🌫️</span>${aqi}</div>
    <div class="srow" style="${cols}"><span class="sico" title="Precipitation chance">🌧️</span>${prec}</div>
  </div>`;
}

function renderScheduled() {
  const v = venueById(STATE.selectedVenue);
  const body = document.getElementById("scheduled-body");
  if (!v) { body.innerHTML = ""; return; }
  const cur = v.current || {};
  const practice = v.practice_hour_iso
    ? `Practice hour: <strong>${new Date(v.practice_hour_iso).toLocaleTimeString([], {hour:"numeric"})}</strong> — ${chip(v.practice_status)}`
    : `<span class="warn">No matched practice today — showing current conditions</span>`;
  const primary = (v.reasons && v.reasons[0]) ? v.reasons[0].detail : "Conditions normal";
  body.innerHTML = `
    <div class="row">${chip(v.status, true)}<span class="reason">${primary}</span></div>
    <p class="reason">${practice}</p>
    <div class="row">
      <span class="metric">WBGT ${num(cur.wbgt && cur.wbgt.value, "°F")}</span>
      <span class="metric">AQI ${num(cur.aqi && cur.aqi.value)} ${cur.aqi && cur.aqi.extra ? "("+cur.aqi.extra.pollutant+")" : ""}</span>
      <span class="metric">Temp ${num(cur.temp && cur.temp.value, "°F")}</span>
      <span class="metric">Wind ${num(cur.wind && cur.wind.value, " mph")}</span>
    </div>
    ${cur.aqi_forecast ? `<p class="reason">Forecast AQI: ${num(cur.aqi_forecast.value)} — <em>forecast, verify with current reading</em></p>` : ""}
    ${(v.flags||[]).map(f=>`<p class="reason warn">⚑ ${f}</p>`).join("")}
    <h3>Next 12 hours — 🌡️ WBGT · 🌫️ AQI · 🌧️ precip</h3>
    ${strip(v.hours || [])}`;
}

function renderBoard() {
  const body = document.getElementById("board-body");
  const venues = [...STATE.data.venues];
  venues.sort((a, b) => STATE.sortWorst
    ? ORDER[a.status] - ORDER[b.status]
    : a.name.localeCompare(b.name));
  body.innerHTML = venues.map(v => {
    const cur = v.current || {};
    const dist = cur.aqi && cur.aqi.distance_mi != null ? ` · ${cur.aqi.distance_mi} mi` : "";
    const poll = cur.aqi && cur.aqi.extra ? ` ${cur.aqi.extra.pollutant}` : "";
    return `<div class="venue-row" data-id="${v.venue_id}">
      <div class="row">
        ${chip(v.status)}
        <span class="name">${v.name}</span>
        <span class="metric">WBGT ${num(cur.wbgt && cur.wbgt.value)}</span>
        <span class="metric">AQI ${num(cur.aqi && cur.aqi.value)}${poll}${dist}</span>
        ${v.practice_hour_iso ? chip(v.practice_status) : ""}
        ${(v.flags||[]).length ? `<span class="warn">⚑${v.flags.length}</span>` : ""}
      </div>
      <div class="expand">
        ${strip(v.hours || [])}
        <p class="reason">Inputs: temp ${num(cur.temp&&cur.temp.value,"°F")}, RH ${num(cur.rh&&cur.rh.value,"%")},
          wind ${num(cur.wind&&cur.wind.value," mph")}, GHI ${num(cur.ghi&&cur.ghi.value," W/m²")}
          ${cur.aqi_purpleair && cur.aqi_purpleair.value!=null ? `· PurpleAir AQI ${cur.aqi_purpleair.value} (${cur.aqi_purpleair.distance_mi} mi)` : ""}</p>
        <p class="reason">Sources: ${cur.temp&&cur.temp.station_or_monitor||"?"} / ${cur.aqi&&cur.aqi.source||"?"} · fetched ${cur.aqi&&cur.aqi.fetched_at||"?"}</p>
      </div></div>`;
  }).join("");
  body.querySelectorAll(".venue-row").forEach(row =>
    row.addEventListener("click", () => row.classList.toggle("open")));
}

function render() {
  staleness(STATE.data.generated_at);
  renderVenuePicker();
  renderScheduled();
  renderBoard();
}

document.getElementById("sort-toggle").addEventListener("click", (e) => {
  STATE.sortWorst = !STATE.sortWorst;
  e.target.textContent = STATE.sortWorst ? "Sort: worst-first" : "Sort: A–Z";
  renderBoard();
});

load();
setInterval(load, 5 * 60 * 1000);  // refresh every 5 min
