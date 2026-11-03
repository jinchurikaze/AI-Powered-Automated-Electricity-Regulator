"""Rule-based energy-saving recommendations (SRS 7.4.4, AD-07)."""
from __future__ import annotations

import re


def peso(v: float) -> str:
    return ("−" if v < 0 else "") + "₱{:,.2f}".format(abs(v))


def recommendations(appliances, ranking, cycle_kwh, rate, days_left, fc, limit_peso, bill_gap=None, bill_id=None,
                    day_key="", cycle_key="", feedback=None, now_ts=None):
    """ranking: list of (appliance, kWh) sorted high → low. fc: forecast dict with projCost.
    Tips that keep the user within the limit come first, then by pesos saved; tips dismissed in the
    last 30 days are hidden (REQ-REC-4)."""
    out = []
    rk = [(a, k) for a, k in ranking if k > 0]
    if fc.get("ok") and limit_peso and fc["projCost"] > limit_peso and rate > 0:
        days = max(1, days_left)
        cut = (fc["projCost"] - limit_peso) / rate / days
        out.append({"key": "stay-" + cycle_key, "title": f"Cut about {cut:.1f} kWh a day to stay within {peso(limit_peso)}",
                    "body": f"The forecast is {peso(fc['projCost'] - limit_peso)} over your limit with {days} days left. "
                            "Turn on the usage plan to get a daily allowance per appliance.",
                    "kwh": cut * days, "stay": True})
    if fc.get("ok") and fc.get("perDegree") is not None and fc["avgNextT"] - fc["avgPastT"] >= 0.8 and fc["perDegree"] > 0.2:
        out.append({"key": "heat-" + day_key, "title": f"A hotter week is coming ({round(fc['avgNextT'])}°C average high)",
                    "body": f"Each 1°C hotter adds about {fc['perDegree']:.1f} kWh a day in your home. "
                            "Set the air conditioner to 25°C and use the fan first.",
                    "kwh": fc["perDegree"] * 7 * 0.5})
    if rk and not rk[0][0]["essential"]:
        a, k = rk[0]
        out.append({"key": "less1-" + str(a["id"]), "title": f"{a['type']}: use it 1 hour less per day",
                    "body": f"It is your top appliance this cycle ({round(k / cycle_kwh * 100)}% of use).",
                    "kwh": a["watt"] * 30 / 1000})
    for a in appliances:
        t = a["type"]
        if re.search("television|computer|laptop", t, re.I):
            out.append({"key": f"standby-{a['id']}", "title": f"{t}: unplug when not in use",
                        "body": "Cuts about 2 W of standby power for 20 hours a day.", "kwh": 2 * 20 * 30 / 1000})
        if re.search("washing", t, re.I):
            out.append({"key": f"loads-{a['id']}", "title": f"{t}: wash full loads only",
                        "body": "One less load a week (about 1 hour of running time).", "kwh": a["watt"] * 4 / 1000})
        if re.search("fan", t, re.I) and a["hours"] >= 6:
            out.append({"key": f"fan-{a['id']}", "title": f"{t}: use the timer at night",
                        "body": "Let it switch off 2 hours earlier after you fall asleep.", "kwh": a["watt"] * 2 * 30 / 1000})
    if bill_gap is not None and bill_gap > 0:
        out.append({"key": f"gap-{bill_id}", "title": f"Find the {bill_gap:,.0f} kWh your last bill shows but the app did not record",
                    "body": "Check standby loads (chargers, set-top boxes) and appliances you have not added or logged.",
                    "kwh": bill_gap * 0.3})
    over = fc["projCost"] - limit_peso if fc.get("ok") and limit_peso else 0
    for o in out:
        o["peso"] = o["kwh"] * rate
        o["fixes"] = over > 0 and o["peso"] >= over
        o.setdefault("stay", False)
    feedback = feedback or {}

    def hidden(o):
        f = feedback.get(o["key"])
        return f and f["status"] == "DISMISSED" and now_ts is not None and (now_ts - f["ts"]).days < 30

    res = [o for o in out if not hidden(o)]
    res.sort(key=lambda o: (-((2 if o["stay"] else 0) + (1 if o["fixes"] else 0)), -o["peso"]))
    for o in res:
        o["status"] = (feedback.get(o["key"]) or {}).get("status", "NEW")
    return res
