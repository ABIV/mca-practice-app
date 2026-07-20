from pipeline.models import Signal, HourPoint, VenueConditions, UNKNOWN, GO


def test_signal_known_to_dict():
    s = Signal(value=42, status="ok", source="AirNow",
               station_or_monitor="Minneapolis", distance_mi=3.1,
               fetched_at="2026-07-19T14:00:00-05:00")
    d = s.to_dict()
    assert d["value"] == 42
    assert d["source"] == "AirNow"
    assert d["distance_mi"] == 3.1
    assert d["status"] == "ok"


def test_signal_unknown_never_has_number():
    s = Signal.unknown("AirNow fetch failed", source="AirNow")
    d = s.to_dict()
    assert d["status"] == "unknown"
    assert d["value"] is None
    assert "AirNow fetch failed" in d["reason"]


def test_venue_conditions_to_dict_roundtrip():
    vc = VenueConditions(venue_id="wolly", name="Woolly Trails", status=GO, reasons=[])
    d = vc.to_dict()
    assert d["venue_id"] == "wolly"
    assert d["status"] == GO
    assert "hours" in d
