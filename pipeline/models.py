"""conditions.json data contract. Every value is wrapped in a Signal carrying
provenance and a status; a failed fetch yields Signal.unknown (value None)."""
from dataclasses import dataclass, field, asdict
from typing import Any, Optional

GO = "GO"
CAUTION = "CAUTION"
CANCELLED = "CANCELLED"
UNKNOWN = "UNKNOWN"

@dataclass
class Signal:
    value: Any = None
    status: str = "ok"           # "ok" | "unknown" | "suspect"
    source: Optional[str] = None
    station_or_monitor: Optional[str] = None
    distance_mi: Optional[float] = None
    fetched_at: Optional[str] = None
    reason: Optional[str] = None
    extra: dict = field(default_factory=dict)

    @classmethod
    def unknown(cls, reason: str, source: Optional[str] = None,
                station_or_monitor: Optional[str] = None) -> "Signal":
        return cls(value=None, status="unknown", source=source,
                   station_or_monitor=station_or_monitor, reason=reason)

    def to_dict(self) -> dict:
        d = {"value": self.value, "status": self.status, "source": self.source,
             "station_or_monitor": self.station_or_monitor,
             "distance_mi": self.distance_mi, "fetched_at": self.fetched_at}
        if self.reason:
            d["reason"] = self.reason
        if self.extra:
            d["extra"] = self.extra
        return d

@dataclass
class HourPoint:
    time_iso: str
    wbgt_f: Optional[float] = None
    wbgt_suspect: Optional[float] = None      # WBGT computed with cloud-reduced GHI, if suspect
    aqi_forecast: Optional[int] = None
    precip_pct: Optional[int] = None
    weather_code: Optional[str] = None
    status: str = UNKNOWN
    reasons: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)

@dataclass
class VenueConditions:
    venue_id: str
    name: str
    status: str = UNKNOWN
    reasons: list = field(default_factory=list)
    practice_hour_iso: Optional[str] = None
    practice_status: str = UNKNOWN
    practice_reasons: list = field(default_factory=list)
    current: dict = field(default_factory=dict)   # {"temp": Signal, "rh": Signal, ...} -> dicts
    hours: list = field(default_factory=list)      # list[HourPoint dicts]
    alerts: list = field(default_factory=list)
    flags: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "venue_id": self.venue_id, "name": self.name,
            "status": self.status, "reasons": self.reasons,
            "practice_hour_iso": self.practice_hour_iso,
            "practice_status": self.practice_status,
            "practice_reasons": self.practice_reasons,
            "current": self.current, "hours": self.hours,
            "alerts": self.alerts, "flags": self.flags,
        }
