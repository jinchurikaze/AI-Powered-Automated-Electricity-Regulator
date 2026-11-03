"""Usage plan (SRS Feature 10) and what-if simulator (Feature 12)."""
from __future__ import annotations


def usage_plan(appliances, avg_daily_kwh: dict, used_today_kwh: dict, limit_kwh: float,
               cycle_kwh_before_today: float, days_left: int) -> dict:
    """Daily budget = (limit kWh − cycle kWh before today) ÷ days left.
    Non-essential appliances get their usual hours × scale, where
    scale = (budget − essential usual kWh) ÷ non-essential usual kWh, limited to 0–1 (REQ-REG-1, -2)."""
    days = max(1, days_left)
    remaining = limit_kwh - cycle_kwh_before_today
    daily = remaining / days
    essential = sum(avg_daily_kwh.get(a["id"], 0) for a in appliances if a["essential"])
    flex = [a for a in appliances if not a["essential"] and avg_daily_kwh.get(a["id"], 0) > 0]
    usual_flex = sum(avg_daily_kwh[a["id"]] for a in flex)
    scale = max(0.0, min(1.0, (daily - essential) / usual_flex)) if usual_flex > 0 else 1.0
    items = []
    for a in flex:
        kw = a["watt"] / 1000
        usual_h = avg_daily_kwh[a["id"]] / kw
        allow_h = usual_h * scale
        used_h = used_today_kwh.get(a["id"], 0) / kw
        items.append({"a": a, "usualH": usual_h, "allowH": allow_h, "usedH": used_h, "leftH": allow_h - used_h})
    return {"daily": daily, "essential": essential, "flex": daily - essential, "scale": scale,
            "needed": scale < 0.999, "items": items, "daysLeft": days, "remaining": remaining}


def what_if(appliances, usual_hours: dict, changes: dict, rate: float,
            saving_pct: float = 35, extra_cost: float = 12000) -> dict:
    """changes: {appliance id: {"dh": hours change per day, "inv": bool}} (REQ-WIF-1 to 3).
    Monthly change (kWh) = W × change in hours × 30 ÷ 1,000; an inverter saves saving_pct of the new kWh."""
    d_kwh = inv_save = extra = 0.0
    rows = []
    for a in appliances:
        c = changes.get(a["id"]) or {"dh": 0, "inv": False}
        usual = usual_hours.get(a["id"], 0)
        new_h = max(0.0, usual + c.get("dh", 0))
        base = a["watt"] * usual * 30 / 1000
        k = a["watt"] * new_h * 30 / 1000
        s = 0.0
        if c.get("inv"):
            s = k * saving_pct / 100
            k -= s
            extra += extra_cost
        d_kwh += k - base
        inv_save += s
        rows.append({"a": a, "usual": usual, "newH": new_h, "delta": k - base})
    inv_peso = inv_save * rate
    return {"dK": d_kwh, "monthlyPeso": d_kwh * rate, "payback": (extra / inv_peso) if inv_peso > 0 else None,
            "extra": extra, "invPeso": inv_peso, "rows": rows}
