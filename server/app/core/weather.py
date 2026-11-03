"""Daily high temperatures (SRS Feature 8).

Real users: Open-Meteo (free, no API key) for Legazpi City. The sample household uses simulated
temperatures so the demo always shows the same numbers.
"""
from __future__ import annotations

import json
import math
import urllib.parse
import urllib.request
from datetime import date, datetime

LAT, LON = 13.14, 123.74  # Legazpi City

_SAMPLE_NEXT = {"2026-10-31": 33, "2026-11-01": 34, "2026-11-02": 34, "2026-11-03": 33,
                "2026-11-04": 32, "2026-11-05": 31, "2026-11-06": 31, "2026-11-07": 30}


def simulated_high(d: date | datetime) -> float:
    """Same formula as the sample household in the web prototype v2."""
    d = date(d.year, d.month, d.day)
    key = d.isoformat()
    if key in _SAMPLE_NEXT:
        return float(_SAMPLE_NEXT[key])
    k = (d - date(1970, 1, 1)).days
    x = math.sin(k * 12.9898) * 43758.5453
    x = x - math.floor(x)
    hot = date(2026, 10, 24) <= d < date(2026, 10, 31)
    v = (33.6 if hot else 30.8) + (x - 0.5) * 2
    return float(math.floor(v + 0.5))  # JavaScript Math.round


def parse_open_meteo(body: str) -> dict[str, float]:
    j = json.loads(body)
    daily = j.get("daily") or {}
    out = {}
    for d, t in zip(daily.get("time") or [], daily.get("temperature_2m_max") or []):
        if isinstance(t, (int, float)):
            out[d] = float(t)
    return out


def fetch_open_meteo(lat: float = LAT, lon: float = LON, past_days: int = 35, timeout: float = 10) -> dict[str, float]:
    """Returns {'yyyy-mm-dd': high °C}; an empty dict when offline (the forecast then uses the other models)."""
    q = urllib.parse.urlencode({"latitude": lat, "longitude": lon, "daily": "temperature_2m_max",
                                "timezone": "Asia/Manila", "past_days": past_days, "forecast_days": 8})
    try:
        with urllib.request.urlopen("https://api.open-meteo.com/v1/forecast?" + q, timeout=timeout) as r:
            return parse_open_meteo(r.read().decode("utf-8"))
    except Exception:
        return {}
