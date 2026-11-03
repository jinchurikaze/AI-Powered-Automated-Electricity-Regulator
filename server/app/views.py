"""Screen data: what each screen shows, built from a Household. Used by both the REST API
(the Flutter app renders it) and the web pages, so both always show the same numbers."""
from __future__ import annotations

from datetime import timedelta

from .core import calc
from .format import short_date

DAY = timedelta(days=1)


def appliance_out(h, a):
    end = h.now + timedelta(seconds=1)
    t = calc.day_start(h.now)
    out = {k: a[k] for k in ("id", "type", "brand", "model", "watt", "location", "hours", "essential")}
    out["timerStart"] = a["timer"]
    out["running"] = a["timer"] is not None
    out["elapsedH"] = (h.now - a["timer"]).total_seconds() / 3600 if a["timer"] else 0
    out["todayKwh"] = h.sum_kwh(t, end, a["id"])
    out["loggedToday"] = h.logged_today(a["id"])
    return out


def plan_out(h, p):
    if p is None:
        return None
    return {"active": bool(h.user["plan_active"]), "daily": p["daily"], "essential": p["essential"], "scale": p["scale"],
            "needed": p["needed"], "daysLeft": p["daysLeft"],
            "items": [{"applianceId": i["a"]["id"], "type": i["a"]["type"], "usualH": i["usualH"], "allowH": i["allowH"],
                       "usedH": i["usedH"], "leftH": i["leftH"]} for i in p["items"]]}


def meta(h):
    return {"now": h.now, "simulated": h.simulated, "unread": h.unread(), "email": h.user["email"], "rate": h.rate,
            "cycleDay": h.user["cycle_day"], "alertsEnabled": bool(h.user["alerts_enabled"]),
            "planActive": bool(h.user["plan_active"])}


def home(h):
    st = h.stats()
    fc = h.forecast()
    lim = next((x for x in h.limit_status() if x["key"] == "monthly"), None)
    rank = [(a, k) for a, k in h.ranking() if k > 0][:3]
    tips = h.recommendations()
    plan = h.usage_plan() if h.user["plan_active"] else None
    return {**meta(h),
            "running": [appliance_out(h, a) for a in h.appliances if a["timer"] is not None],
            "notLogged": sum(1 for a in h.appliances if a["timer"] is None and not a["essential"] and not h.logged_today(a["id"])),
            "todayKwh": st["td"], "todayCost": h.cost(st["td"]), "cycleKwh": st["cyc"], "cycleCost": h.cost(st["cyc"]),
            "dayIndex": st["di"], "cycleDays": st["cycle"].days,
            "limit": lim, "limitPeso": h.limit_peso(),
            "forecastCost": fc["projCost"] if fc.get("ok") else st["projCost"],
            "top": [{"type": a["type"], "kwh": k, "share": k / st["cyc"] * 100 if st["cyc"] else 0} for a, k in rank],
            "tip": tips[0] if tips else None,
            "plan": plan_out(h, plan) if plan and plan["needed"] else None}


def appliances(h):
    return {**meta(h), "appliances": [appliance_out(h, a) for a in h.appliances]}


def appliance_detail(h, aid):
    a = h.appliance(aid)
    c = h.cycle()
    end = h.now + timedelta(seconds=1)
    it = h.plan_item(a["id"])
    cyc = h.sum_kwh(c.start, end, a["id"])
    return {**meta(h), "appliance": appliance_out(h, a), "cycleKwh": cyc, "cycleCost": h.cost(cyc),
            "plan": None if it is None else {"allowH": it["allowH"], "usedH": it["usedH"], "leftH": it["leftH"]},
            "recent": [{"ts": u["ts"], "hours": u["h"], "kwh": u["kwh"], "src": u["src"]} for u in h.recent_entries(a["id"])]}


def usage(h, view="daily"):
    st = h.stats()
    if view == "monthly":
        bars = [{"label": "This cycle" if x["current"] else short_date(x["start"]) + " cycle", "kwh": x["kwh"],
                 "current": x["current"]} for x in h.cycle_totals()]
    else:
        series = h.daily_series(6)
        bars = [{"label": str(x["t"].day), "kwh": x["k"], "current": False} for x in series]
        bars.append({"label": "Today", "kwh": st["td"], "current": True})
    rank = [(a, k) for a, k in h.ranking() if k > 0]
    return {**meta(h), "view": view, "bars": bars, "cycleKwh": st["cyc"], "cycleCost": h.cost(st["cyc"]),
            "change": h.change_vs_last_cycle(), "projKwh": st["proj"], "projCost": st["projCost"], "dayIndex": st["di"],
            "cycleDays": st["cycle"].days,
            "shares": [{"id": a["id"], "type": a["type"], "kwh": k, "cost": h.cost(k), "share": k / st["cyc"] * 100 if st["cyc"] else 0,
                        "aboveUsual": h.above_usual(a["id"])} for a, k in rank]}


def save(h):
    fc = h.forecast()
    p = h.usage_plan()
    out = {**meta(h), "forecast": None, "need": None, "plan": plan_out(h, p), "tips": h.recommendations(),
           "limitPeso": h.limit_peso()}
    if fc.get("ok"):
        out["forecast"] = {"model": fc["model"], "mae": fc["mae"], "perDegree": fc["perDegree"], "projKwh": fc["projK"],
                           "projCost": fc["projCost"], "next": [{"day": x["t"], "kwh": x["k"], "tmax": x["T"]} for x in fc["next"]]}
    else:
        out["need"] = fc["need"]
    return out


def what_if(h, result=None, changes=None, saving=35, extra=12000):
    usual = h.usual_hours()
    return {**meta(h), "appliances": [{"id": a["id"], "type": a["type"], "watt": a["watt"], "usualH": usual[a["id"]],
                                        "inverterOption": any(w in a["type"].lower() for w in ("air", "refrigerator")),
                                        "dh": (changes or {}).get(a["id"], {}).get("dh", 0),
                                        "inv": (changes or {}).get(a["id"], {}).get("inv", False)}
                                       for a in h.appliances if usual[a["id"]] > 0],
            "savingPct": saving, "extraCost": extra,
            "result": None if result is None else {"monthlyKwh": result["dK"], "monthlyPeso": result["monthlyPeso"],
                                                   "payback": result["payback"]}}


def check(h):
    bc = h.last_bill_check()
    mc = h.meter_check()
    return {**meta(h),
            "bill": None if bc is None else {"id": bc["bill"]["id"], "start": bc["bill"]["start"], "end": bc["bill"]["end"],
                                             "kwh": bc["billK"], "amount": bc["bill"]["amount"], "src": bc["bill"]["src"],
                                             "recordedKwh": bc["appK"], "missingKwh": bc["gapK"], "missingPeso": bc["gapPeso"],
                                             "coverage": bc["coverage"], "rate": bc["eff"],
                                             "rateDiffers": abs(bc["eff"] - h.rate) >= 0.01},
            "meter": None if mc is None else {"from": mc["a"]["ts"], "to": mc["b"]["ts"], "measured": mc["measured"],
                                              "recorded": mc["appK"], "missing": mc["gap"], "coverage": mc["coverage"]},
            "readings": list(reversed(h.meter))[:4]}


def limits(h):
    return {**meta(h), "monthly": h.limits["monthly"], "daily": h.limits["daily"], "alerts": h.alerts}
