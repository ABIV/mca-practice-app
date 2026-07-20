"""TeamSnap iCal → today's events matched to venues (server-side; avoids CORS)."""
from datetime import datetime
from zoneinfo import ZoneInfo
from pipeline import http

CENTRAL = ZoneInfo("America/Chicago")
ICAL = "http://ical-cdn.teamsnap.com/team_schedule/085d0f1e-1abe-42ca-999e-ef79981f7bba.ics"

def _parse_dt(value):
    v = value.strip()
    if v.endswith("Z"):
        dt = datetime.strptime(v, "%Y%m%dT%H%M%SZ").replace(tzinfo=ZoneInfo("UTC"))
    elif "T" in v:
        dt = datetime.strptime(v[:15], "%Y%m%dT%H%M%S").replace(tzinfo=CENTRAL)
    else:
        dt = datetime.strptime(v[:8], "%Y%m%d").replace(tzinfo=CENTRAL)
    return dt.astimezone(CENTRAL)

def _match(location, venues):
    loc = (location or "").lower()
    for v in venues:
        for key in ("name", "short", "city"):
            val = (v.get(key) or "").lower()
            if val and val in loc:
                return v["id"]
    return None

def fetch_today(venues, now=None):
    now = now or datetime.now(CENTRAL)
    text = http.get_text(ICAL, params={"_": int(now.timestamp())})
    events = []
    for block in text.split("BEGIN:VEVENT")[1:]:
        if "END:VEVENT" not in block:
            continue
        fields = {}
        for line in block.splitlines():
            if line.startswith("SUMMARY:"):
                fields["title"] = line[len("SUMMARY:"):].strip()
            elif line.startswith("LOCATION:"):
                fields["location"] = line[len("LOCATION:"):].strip().replace("\\,", ",")
            elif line.startswith("DTSTART"):
                fields["start"] = _parse_dt(line.split(":", 1)[1])
        start = fields.get("start")
        if not start or start.date() != now.date():
            continue
        events.append({"title": fields.get("title", "Practice"),
                       "location": fields.get("location", ""),
                       "start_iso": start.isoformat(timespec="seconds"),
                       "venue_id": _match(fields.get("location"), venues)})
    return events
