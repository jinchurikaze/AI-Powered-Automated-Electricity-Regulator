"""Weather-aware forecasting (SRS 7.4.4, AD-06).

Three models are fitted on the daily kWh series, each adjusted by day-of-week factors:
a 7-day moving average, a linear trend, and a linear regression on the daily high temperature.
With 14 or more days, each is fitted on all but the last 7 days and the one with the lowest
mean absolute error (MAE) on those 7 days is used.
"""
from __future__ import annotations

from datetime import datetime, timedelta

DAY = timedelta(days=1)
MIN_DAYS = 7  # BR-3
MODELS = ("7-day moving average", "Trend (linear regression)", "Weather-aware regression")


def _dow(t: datetime) -> int:
    return t.weekday()


def _fit_line(xs, ys):
    n = len(xs)
    sx, sy = sum(xs), sum(ys)
    sxy = sum(x * y for x, y in zip(xs, ys))
    sxx = sum(x * x for x in xs)
    den = n * sxx - sx * sx
    b = (n * sxy - sx * sy) / den if den else 0.0
    return (sy - b * sx) / n, b


def _factors(train):
    mean = sum(x["k"] for x in train) / len(train) or 1
    f = {}
    for d in range(7):
        xs = [x["k"] for x in train if _dow(x["t"]) == d]
        f[d] = (sum(xs) / len(xs)) / mean if xs else 1.0
    return f


def fit_moving_average(train, temp_for):
    last = train[-7:]
    base = sum(x["k"] for x in last) / min(7, len(train))
    f = _factors(train)
    return lambda t: base * f[_dow(t)]


def fit_trend(train, temp_for):
    f = _factors(train)
    t0 = train[0]["t"]
    a, b = _fit_line([(x["t"] - t0).days for x in train], [x["k"] / f[_dow(x["t"])] for x in train])
    return lambda t: max(0.0, (a + b * (t - t0).days) * f[_dow(t)])


def fit_weather(train, temp_for):
    f = _factors(train)
    a, b = _fit_line([x["T"] for x in train], [x["k"] / f[_dow(x["t"])] for x in train])

    def p(t):
        T = temp_for(t)
        if T is None:
            T = 30.0
        return max(0.0, (a + b * T) * f[_dow(t)])

    p.slope = b
    return p


_FITS = {MODELS[0]: fit_moving_average, MODELS[1]: fit_trend, MODELS[2]: fit_weather}


def forecast(series, today: datetime, now: datetime, cycle_end: datetime, cycle_kwh: float, temp_for):
    """series: list of {"t": day, "k": kWh, "T": °C or None}, oldest first, complete days only.

    Returns a dict like the web prototype's forecast(): ok, next (7 days), model, mae, projK,
    perDegree, avgNextT, avgPastT. Costs are added by the caller.
    """
    if len(series) < MIN_DAYS:
        return {"ok": False, "need": MIN_DAYS - len(series)}
    nexts = [today + i * DAY for i in range(1, 8)]
    weather_ok = all(x["T"] is not None for x in series) and all(temp_for(d) is not None for d in nexts)
    names = list(MODELS) if weather_ok else list(MODELS[:2])
    best, mae = names[0], None
    if len(series) >= 14:
        train, test = series[:-7], series[-7:]
        best_err = float("inf")
        for name in names:
            p = _FITS[name](train, temp_for)
            err = sum(abs(p(x["t"]) - x["k"]) for x in test) / 7
            if err < best_err:
                best_err, best = err, name
        mae = best_err
    model = _FITS[best](series, temp_for)
    slope = fit_weather(series, temp_for).slope if weather_ok else None
    nxt = [{"t": d, "k": model(d), "T": temp_for(d)} for d in nexts]
    frac = 1 - (now - today).total_seconds() / 86400
    rest = model(today) * frac
    d = today + DAY
    while d < cycle_end:
        rest += model(d)
        d += DAY
    avg_next = sum(x["T"] for x in nxt) / 7 if weather_ok else None
    avg_past = sum(x["T"] for x in series[-7:]) / 7 if weather_ok else None
    return {"ok": True, "next": nxt, "model": best, "mae": mae, "projK": cycle_kwh + rest,
            "perDegree": slope, "avgNextT": avg_next, "avgPastT": avg_past, "days": len(series)}
