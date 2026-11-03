"""Philippine number and date formats (NFR-LOC-2, NFR-LOC-3) and JSON serialization."""
from __future__ import annotations

from datetime import date, datetime

MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def peso(v) -> str:
    v = float(v or 0)
    return ("−" if v < -0.004 else "") + "₱{:,.2f}".format(abs(v))


def signed_peso(v) -> str:
    return ("+" if v > 0.004 else "") + peso(v)


def kwh(v, d=2) -> str:
    v = float(v or 0)
    s = "{:,.{d}f}".format(abs(v), d=d)
    return ("−" if v < 0 and s.strip("0.,") else "") + s + " kWh"


def hours(h) -> str:
    m = round(float(h or 0) * 60)
    neg = m < 0
    m = abs(m)
    s = f"{m} min" if m < 60 else (f"{m // 60} h" if m % 60 == 0 else f"{m // 60} h {m % 60} min")
    return ("−" if neg else "") + s


def short_date(t) -> str:
    if isinstance(t, str):
        t = date.fromisoformat(t[:10])
    return f"{MONTHS[t.month - 1]} {t.day}"


def long_date(t) -> str:
    if isinstance(t, str):
        t = date.fromisoformat(t[:10])
    return f"{MONTHS[t.month - 1]} {t.day}, {t.year}"


def clock(t) -> str:
    if isinstance(t, str):
        t = datetime.fromisoformat(t)
    h = t.hour % 12 or 12
    return f"{h}:{t.minute:02d} {'PM' if t.hour >= 12 else 'AM'}"


def date_time(t) -> str:
    if isinstance(t, str):
        t = datetime.fromisoformat(t)
    return f"{long_date(t)}, {clock(t)}"


def register_filters(app):
    for name, fn in {"peso": peso, "signed_peso": signed_peso, "kwh": kwh, "hours": hours, "short_date": short_date,
                     "long_date": long_date, "clock": clock, "date_time": date_time}.items():
        app.jinja_env.filters[name] = fn


def jsonable(o):
    """Converts datetimes and nested structures for JSON responses."""
    if isinstance(o, datetime):
        return o.isoformat(timespec="seconds")
    if isinstance(o, date):
        return o.isoformat()
    if isinstance(o, dict):
        return {k: jsonable(v) for k, v in o.items() if not callable(v)}
    if isinstance(o, (list, tuple)):
        return [jsonable(v) for v in o]
    if isinstance(o, float):
        return round(o, 4)
    return o
