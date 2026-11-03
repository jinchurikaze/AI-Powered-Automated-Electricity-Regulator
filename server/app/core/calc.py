"""Consumption and cost calculations (SRS 7.4.4). Pure functions, unit tested.

A usage record is a dict: {"a": appliance id, "ts": datetime, "kwh": float, "h": float, "src": "TIMER"|"LOGGED"}.
"""
from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date, datetime, timedelta

DAY = timedelta(days=1)


def energy_kwh(watts: float, hours: float) -> float:
    """REQ-MON-2: energy (kWh) = W × h ÷ 1,000."""
    return watts * hours / 1000.0


def cost(kwh: float, rate: float) -> float:
    """REQ-CST-1: cost (₱) = kWh × rate."""
    return kwh * rate


def day_start(t: datetime) -> datetime:
    return datetime(t.year, t.month, t.day)


def day_key(t: datetime | date) -> str:
    return f"{t.year:04d}-{t.month:02d}-{t.day:02d}"


@dataclass(frozen=True)
class Cycle:
    start: datetime
    end: datetime  # exclusive

    @property
    def days(self) -> int:
        return (self.end - self.start).days

    @property
    def key(self) -> str:
        return day_key(self.start)


def _clamp(year: int, month: int, day: int) -> int:
    return min(day, calendar.monthrange(year, month)[1])


def cycle_of(t: datetime, start_day: int) -> Cycle:
    """The billing cycle that contains t, for a cycle starting on start_day (clamped to short months)."""
    y, m = t.year, t.month
    start = datetime(y, m, _clamp(y, m, start_day))
    if t < start:
        m -= 1
        if m < 1:
            m, y = 12, y - 1
        start = datetime(y, m, _clamp(y, m, start_day))
    m2, y2 = m + 1, y
    if m2 > 12:
        m2, y2 = 1, y2 + 1
    return Cycle(start, datetime(y2, m2, _clamp(y2, m2, start_day)))


def sum_kwh(records, start: datetime, end: datetime, appliance_id=None) -> float:
    return sum(r["kwh"] for r in records
               if start <= r["ts"] < end and (appliance_id is None or r["a"] == appliance_id))


def day_index(c: Cycle, now: datetime) -> int:
    return (day_start(now) - c.start).days + 1


def projected_cycle_kwh(cycle_kwh: float, days_elapsed: int, days_in_cycle: int) -> float:
    """REQ-CST-2: (cycle kWh so far ÷ days elapsed) × days in cycle."""
    return 0.0 if days_elapsed <= 0 else cycle_kwh / days_elapsed * days_in_cycle


def percent_used(used: float, limit: float) -> float:
    return 0.0 if limit <= 0 else used / limit * 100


def above_usual(records, appliance_id, now: datetime) -> bool:
    """REQ-HCA-3: this week's use is more than 20% above the average week of the previous four."""
    t = day_start(now)
    week = sum_kwh(records, t - 7 * DAY, t, appliance_id)
    prev = sum_kwh(records, t - 35 * DAY, t - 7 * DAY, appliance_id) / 4
    return prev > 0 and week > prev * 1.2


def split_by_day(start: datetime, end: datetime):
    """Yields (day_end_timestamp, hours) for each calendar day covered by [start, end)."""
    s = start
    while s < end:
        nxt = day_start(s) + DAY
        e = min(end, nxt)
        h = (e - s).total_seconds() / 3600
        if h > 0:
            yield e - timedelta(seconds=1), h
        s = e
