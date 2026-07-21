import pathlib, datetime
from zoneinfo import ZoneInfo
from pipeline.sources import schedule

FIX = pathlib.Path(__file__).parent / "fixtures" / "schedule.ics"
VENUES = [{"id":"elm-creek","name":"Elm Creek Park Reserve","short":"Elm Creek","city":"Maple Grove, MN"},
          {"id":"wolly","name":"Woolly Trails","short":"Wolly","city":"St. Croix Falls, WI"}]

def test_matches_today_event(monkeypatch):
    monkeypatch.setattr(schedule.http, "get_text", lambda *a, **k: FIX.read_text())
    now = datetime.datetime(2026, 7, 19, 12, 0, tzinfo=ZoneInfo("America/Chicago"))
    events = schedule.fetch_today(VENUES, now=now)
    assert len(events) == 1
    assert events[0]["venue_id"] == "elm-creek"

def test_unmatched_location_is_none(monkeypatch):
    ics = FIX.read_text().replace("Elm Creek Park Reserve\\, Maple Grove", "Some Random Field")
    monkeypatch.setattr(schedule.http, "get_text", lambda *a, **k: ics)
    now = datetime.datetime(2026, 7, 19, 12, 0, tzinfo=ZoneInfo("America/Chicago"))
    events = schedule.fetch_today(VENUES, now=now)
    assert events[0]["venue_id"] is None

def test_matches_on_title_when_location_is_bare_address(monkeypatch):
    # Real feed: park name is in the TITLE, LOCATION is just a street address.
    ics = ("BEGIN:VCALENDAR\nBEGIN:VEVENT\n"
           "SUMMARY:2026 MTB MV TG ID - Practice- Battle Creek\n"
           "LOCATION:75 Winthrop St S\\, St Paul\\, MN 55119\n"
           "DTSTART:20260719T230000Z\n"
           "END:VEVENT\nEND:VCALENDAR\n")
    venues = [{"id": "battle-creek", "name": "Battle Creek Regional Park",
               "short": "Battle Creek", "city": "St. Paul, MN"}]
    monkeypatch.setattr(schedule.http, "get_text", lambda *a, **k: ics)
    now = datetime.datetime(2026, 7, 19, 12, 0, tzinfo=ZoneInfo("America/Chicago"))
    events = schedule.fetch_today(venues, now=now)
    assert len(events) == 1 and events[0]["venue_id"] == "battle-creek"

def test_unfolds_folded_location(monkeypatch):
    # RFC 5545 folded LOCATION: continuation line begins with a space.
    ics = ("BEGIN:VCALENDAR\nBEGIN:VEVENT\n"
           "SUMMARY:2026 MTB MV TG ID - Practice- Sunfish\n"
           "LOCATION:9532 Stillwater Blvd N Lake El\n mo\\, MN 55042\n"
           "DTSTART:20260719T230000Z\n"
           "END:VEVENT\nEND:VCALENDAR\n")
    venues = [{"id": "sunfish-lake", "name": "Sunfish Lake Park",
               "short": "Sunfish", "city": "Lake Elmo, MN"}]
    monkeypatch.setattr(schedule.http, "get_text", lambda *a, **k: ics)
    now = datetime.datetime(2026, 7, 19, 12, 0, tzinfo=ZoneInfo("America/Chicago"))
    events = schedule.fetch_today(venues, now=now)
    assert len(events) == 1
    assert "Lake Elmo" in events[0]["location"]  # only true if unfolding worked
    assert events[0]["venue_id"] == "sunfish-lake"
