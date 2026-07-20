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
