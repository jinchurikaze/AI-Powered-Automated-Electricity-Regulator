"""Household service: everything one user's app does (SRS Features 1–12).

Loads the user's rows from SQLite, computes summaries, and performs the checks that send alerts,
offer the usage plan, and send plan reminders (SRS 7.4.2). Both the REST API (Flutter app) and the
web pages use this class, so the rules live in one place.
"""
from __future__ import annotations

import random
import re
import secrets
from datetime import date, datetime, timedelta

from werkzeug.security import check_password_hash, generate_password_hash

from .core import bill as billcore
from .core import calc, weather
from .core.forecast import forecast as run_forecast
from .core.plan import usage_plan, what_if
from .core.recommend import peso, recommendations
from .db import parse_ts, ts

DAY = timedelta(days=1)
HOUR = timedelta(hours=1)
MIN = timedelta(minutes=1)
SAMPLE_CLOCK = datetime(2026, 10, 31, 9, 40)
APPLIANCE_TYPES = ["Air conditioner", "Refrigerator", "Electric fan", "Television", "Washing machine",
                   "Rice cooker", "Computer", "Lights", "Water dispenser", "Other"]
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class ValidationError(Exception):
    def __init__(self, errors: dict):
        super().__init__("; ".join(errors.values()))
        self.errors = errors


def fmt_h(h: float) -> str:
    m = round(h * 60)
    if m < 60:
        return f"{m} min"
    return f"{m // 60} h" if m % 60 == 0 else f"{m // 60} h {m % 60} min"


def fmt_limit(v: float, unit: str) -> str:
    return peso(v) if unit == "PESO" else f"{v:,.1f} kWh"


def _num(s, cast=float):
    try:
        return cast(str(s).replace(",", "").strip())
    except (TypeError, ValueError):
        return None


# ======================================================================== accounts

def create_account(db, email, password, rate, cycle_day, monthly_limit="", consent=False, now=None) -> int:
    """UC-01 / REQ-ACC-1 to 4. Returns the new user id; raises ValidationError."""
    e = {}
    email = (email or "").strip().lower()
    if not EMAIL_RE.match(email):
        e["email"] = "Enter a valid email address."
    elif db.execute("SELECT 1 FROM users WHERE email=?", (email,)).fetchone():
        e["email"] = "Email already in use."
    if len(password or "") < 8:
        e["password"] = "Use at least 8 characters."
    r = _num(rate)
    if r is None or r <= 0:
        e["rate"] = "Enter a rate greater than 0."
    d = _num(cycle_day, int)
    if d is None or not 1 <= d <= 31:
        e["cycle_day"] = "Choose a day from 1 to 31."
    lim = None
    if str(monthly_limit or "").strip():
        lim = _num(monthly_limit)
        if lim is None or lim <= 0:
            e["limit"] = "Enter an amount greater than 0, or leave it empty."
    if not consent:
        e["consent"] = "Please agree to the Privacy Notice to continue."
    if e:
        raise ValidationError(e)
    cur = db.execute("INSERT INTO users(email,password_hash,rate,cycle_day,created_at) VALUES (?,?,?,?,?)",
                     (email, generate_password_hash(password), round(r, 2), d, ts(now or datetime.now())))
    uid = cur.lastrowid
    db.execute("INSERT INTO limits VALUES (?,?,?,?,?)", (uid, "monthly", "PESO", lim or 0, 1 if lim else 0))
    db.execute("INSERT INTO limits VALUES (?,?,?,?,?)", (uid, "daily", "KWH", 0, 0))
    db.commit()
    return uid


def authenticate(db, email, password):
    row = db.execute("SELECT id, password_hash FROM users WHERE email=?", ((email or "").strip().lower(),)).fetchone()
    if row and check_password_hash(row["password_hash"], password or ""):
        return row["id"]
    return None


def issue_token(db, uid) -> str:
    tok = secrets.token_urlsafe(32)
    db.execute("INSERT INTO tokens VALUES (?,?,?)", (tok, uid, ts(datetime.now())))
    db.commit()
    return tok


def user_for_token(db, tok):
    row = db.execute("SELECT user_id FROM tokens WHERE token=?", (tok,)).fetchone()
    return row["user_id"] if row else None


# ======================================================================== sample household

def load_sample(db, uid):
    """Replaces the user's data with the sample household of the web prototype (40 days of logged hours,
    ₱12.50/kWh, cycle starting on the 21st, ₱4,000 limit, fan timer running, last bill scanned)."""
    for t in ("appliances", "usage", "alerts", "notifications", "tip_feedback", "plan_offered", "plan_notes",
              "bills", "meter", "limits"):
        db.execute(f"DELETE FROM {t} WHERE user_id=?", (uid,))
    now = SAMPLE_CLOCK
    db.execute("UPDATE users SET rate=12.5, cycle_day=21, alerts_enabled=1, simulated=1, clock=?, plan_active=0 WHERE id=?",
               (ts(now), uid))
    specs = [("Air conditioner", "AirCool", "AC-10", 1000, "Bedroom", 8, 0, None),
             ("Refrigerator", "FrostLine", "FR-7", 150, "Kitchen", 8, 1, None),
             ("Electric fan", "BreezeMax", "EF-16", 60, "Living room", 8, 0, ts(now - 70 * MIN)),
             ("Television", "Viewtek", "TV-43", 120, "Living room", 3, 0, None),
             ("Washing machine", "CleanPro", "WM-7", 500, "Laundry area", 0.5, 0, None)]
    ids = []
    for s in specs:
        cur = db.execute("INSERT INTO appliances(user_id,type,brand,model,watt,location,hours,essential,timer_start) "
                         "VALUES (?,?,?,?,?,?,?,?,?)", (uid, *s))
        ids.append(cur.lastrowid)
    seed = 7

    def r():
        nonlocal seed
        seed = (seed * 1664525 + 1013904223) % 4294967296
        return seed / 4294967296

    skip = {"2026-09-27", "2026-10-03", "2026-10-09", "2026-10-12", "2026-10-19"}
    rows = []
    t = datetime(2026, 9, 21)
    while t < calc.day_start(now):
        dow = t.weekday()  # Mon=0 … Sun=6
        wk = dow >= 5
        T = weather.simulated_high(t)
        for i, s in enumerate(specs):
            if i == 0:
                h = 7.4 + (T - 31) * 0.9 + (1.2 if wk else 0) + (r() - .5) * 1.2
            elif i == 4:
                h = 1.6 if dow in (5, 2) else 0  # Saturday, Wednesday
            else:
                h = s[5] * (0.9 + r() * 0.2)
            if i in (2, 3) and calc.day_key(t) in skip:
                continue
            if h <= 0:
                continue
            rows.append((uid, ids[i], ts(t + 21 * HOUR), round(h, 2), round(s[3] * h / 1000, 3), "LOGGED"))
        t += DAY
    rows.append((uid, ids[0], ts(calc.day_start(now) + 7 * HOUR), 6.5, 6.5, "TIMER"))
    db.executemany("INSERT INTO usage(user_id,appliance_id,ts,hours,kwh,src) VALUES (?,?,?,?,?,?)", rows)
    prev = calc.cycle_of(datetime(2026, 10, 20), 21)
    logged = sum(x[4] for x in rows if prev.start <= parse_ts(x[2]) < prev.end)
    bill_k = float(int(logged * 1.14 + 0.5))
    db.execute("INSERT INTO bills(user_id,start,end,kwh,amount,src,ts) VALUES (?,?,?,?,?,?,?)",
               (uid, calc.day_key(prev.start), calc.day_key(prev.end - DAY), bill_k, round(bill_k * 13.1, 2), "SCAN",
                ts(datetime(2026, 10, 23, 18))))
    db.execute("INSERT INTO meter(user_id,ts,reading) VALUES (?,?,?)", (uid, ts(datetime(2026, 9, 21, 8)), 15230.0))
    db.execute("INSERT INTO meter(user_id,ts,reading) VALUES (?,?,?)", (uid, ts(datetime(2026, 10, 21, 8)), 15230.0 + bill_k))
    db.execute("INSERT INTO limits VALUES (?,?,?,?,?)", (uid, "monthly", "PESO", 4000, 1))
    db.execute("INSERT INTO limits VALUES (?,?,?,?,?)", (uid, "daily", "KWH", 0, 0))
    db.execute("INSERT INTO alerts(user_id,period,threshold,period_key,sent_at,amount,unit) VALUES (?,?,?,?,?,?,?)",
               (uid, "monthly", 80, prev.key, ts(datetime(2026, 10, 14, 19, 5)), 3200, "PESO"))
    db.commit()


def create_demo_user(db) -> int:
    """A fresh sample-household account for the browser demo (no sign-up needed)."""
    email = f"demo-{secrets.token_hex(4)}@example.com"
    cur = db.execute("INSERT INTO users(email,password_hash,created_at) VALUES (?,?,?)",
                     (email, generate_password_hash(secrets.token_urlsafe(12)), ts(datetime.now())))
    load_sample(db, cur.lastrowid)
    return cur.lastrowid


# ======================================================================== household

class Household:
    def __init__(self, db, uid, notify=None):
        self.db, self.uid = db, uid
        self.notify_hook = notify
        self.new_notifications = []
        self.reload()

    # ---------------------------------------------------------------- loading
    def reload(self):
        q = lambda sql, *a: self.db.execute(sql, (self.uid, *a)).fetchall()
        u = self.db.execute("SELECT * FROM users WHERE id=?", (self.uid,)).fetchone()
        if u is None:
            raise KeyError("user not found")
        self.user = dict(u)
        self.simulated = bool(u["simulated"])
        self.now = parse_ts(u["clock"]) if self.simulated and u["clock"] else datetime.now().replace(microsecond=0)
        self.all_appliances = {}
        for r in q("SELECT * FROM appliances WHERE user_id=? ORDER BY id"):
            a = dict(r)
            a["essential"] = bool(a["essential"])
            a["timer"] = parse_ts(a["timer_start"]) if a["timer_start"] else None
            self.all_appliances[a["id"]] = a
        self.appliances = [a for a in self.all_appliances.values() if not a["deleted"]]
        self.usage = [{"id": r["id"], "a": r["appliance_id"], "ts": parse_ts(r["ts"]), "kwh": r["kwh"], "h": r["hours"],
                       "src": r["src"]} for r in q("SELECT * FROM usage WHERE user_id=? ORDER BY ts, id")]
        self.limits = {r["period"]: dict(r) for r in q("SELECT * FROM limits WHERE user_id=?")}
        for p, unit in (("monthly", "PESO"), ("daily", "KWH")):
            self.limits.setdefault(p, {"period": p, "unit": unit, "value": 0, "active": 0})
        self.alerts = [dict(r) for r in q("SELECT * FROM alerts WHERE user_id=? ORDER BY sent_at DESC")]
        self.feedback = {r["key"]: {"status": r["status"], "ts": parse_ts(r["ts"])} for r in q("SELECT * FROM tip_feedback WHERE user_id=?")}
        self.bills = [dict(r) for r in q("SELECT * FROM bills WHERE user_id=? ORDER BY end DESC, id DESC")]
        self.meter = [dict(r) for r in q("SELECT * FROM meter WHERE user_id=? ORDER BY ts, id")]
        self._fc = None

    def appliance(self, aid):
        a = self.all_appliances.get(int(aid)) if str(aid).isdigit() else None
        if a is None or a["deleted"]:
            raise ValidationError({"appliance": "Appliance not found."})
        return a

    def _notify(self, title, body):
        self.db.execute("INSERT INTO notifications(user_id,title,body,ts) VALUES (?,?,?,?)", (self.uid, title, body, ts(self.now)))
        n = {"title": title, "body": body, "ts": self.now}
        self.new_notifications.append(n)
        if self.notify_hook:
            self.notify_hook(n)

    # ---------------------------------------------------------------- weather
    def temp_for(self, d):
        if self.simulated:
            return weather.simulated_high(d)
        row = self.db.execute("SELECT tmax FROM weather WHERE day=?", (calc.day_key(d),)).fetchone()
        return row["tmax"] if row else None

    def refresh_weather(self, fetch=weather.fetch_open_meteo, force=False):
        """Reads Open-Meteo at most every 6 hours (NFR-SUS-1). Not used by the sample household."""
        if self.simulated:
            return 0
        last = self.db.execute("SELECT MAX(fetched_at) m FROM weather").fetchone()["m"]
        if not force and last and datetime.now() - parse_ts(last) < timedelta(hours=6):
            return 0
        temps = fetch()
        stamp = ts(datetime.now())
        for d, t in temps.items():
            self.db.execute("INSERT INTO weather(day,tmax,fetched_at) VALUES (?,?,?) ON CONFLICT(day) DO UPDATE "
                            "SET tmax=excluded.tmax, fetched_at=excluded.fetched_at", (d, t, stamp))
        self.db.commit()
        self._fc = None
        return len(temps)

    # ---------------------------------------------------------------- usage totals
    def live_records(self):
        """Running timers count toward totals while they run, split by day (REQ-MON-1)."""
        out = []
        for a in self.appliances:
            if a["timer"] is None:
                continue
            for e, h in calc.split_by_day(a["timer"], self.now):
                out.append({"a": a["id"], "ts": e, "kwh": a["watt"] * h / 1000, "h": h, "src": "TIMER", "live": True})
        return out

    def records(self):
        return self.usage + self.live_records()

    def sum_kwh(self, start, end, aid=None):
        return calc.sum_kwh(self.records(), start, end, aid)

    @property
    def rate(self):
        return self.user["rate"] or 0.0

    def cost(self, k):
        return calc.cost(k, self.rate)

    def cycle(self):
        return calc.cycle_of(self.now, self.user["cycle_day"] or 1)

    def stats(self):
        c = self.cycle()
        end = self.now + timedelta(seconds=1)
        cyc = self.sum_kwh(c.start, end)
        td = self.sum_kwh(calc.day_start(self.now), end)
        di = calc.day_index(c, self.now)
        proj = calc.projected_cycle_kwh(cyc, di, c.days)
        return {"cycle": c, "cyc": cyc, "td": td, "di": di, "proj": proj, "projCost": self.cost(proj)}

    def ranking(self, start=None, end=None):
        c = self.cycle()
        start = start or c.start
        end = end or self.now + timedelta(seconds=1)
        rows = [(a, self.sum_kwh(start, end, a["id"])) for a in self.appliances]
        rows.sort(key=lambda x: -x[1])
        return rows

    def above_usual(self, aid):
        return calc.above_usual(self.records(), aid, self.now)

    def daily_series(self, days):
        t = calc.day_start(self.now)
        recs = self.records()
        return [{"t": t - i * DAY, "k": calc.sum_kwh(recs, t - i * DAY, t - (i - 1) * DAY), "T": self.temp_for(t - i * DAY)}
                for i in range(days, 0, -1)]

    def cycle_totals(self, n=4):
        c = self.cycle()
        cycles = [c]
        for _ in range(n - 1):
            cycles.insert(0, calc.cycle_of(cycles[0].start - DAY, self.user["cycle_day"] or 1))
        out = []
        for x in cycles:
            end = min(x.end, self.now + timedelta(seconds=1))
            k = self.sum_kwh(x.start, end)
            if k == 0 and x != c:
                continue
            out.append({"start": x.start, "kwh": k, "current": x == c})
        return out

    def change_vs_last_cycle(self):
        c = self.cycle()
        prev = calc.cycle_of(c.start - DAY, self.user["cycle_day"] or 1)
        same = self.sum_kwh(prev.start, prev.start + (self.now - c.start))
        return (self.stats()["cyc"] - same) / same * 100 if same > 0 else None

    # ---------------------------------------------------------------- limits
    def limit_peso(self):
        m = self.limits["monthly"]
        if not m["active"] or m["value"] <= 0:
            return None
        return m["value"] if m["unit"] == "PESO" else m["value"] * self.rate

    def limit_status(self):
        st = self.stats()
        res = []
        m, d = self.limits["monthly"], self.limits["daily"]
        if m["active"] and m["value"] > 0:
            used = self.cost(st["cyc"]) if m["unit"] == "PESO" else st["cyc"]
            res.append({"key": "monthly", "period": st["cycle"].key, "used": used, "limit": m["value"], "unit": m["unit"],
                        "pct": used / m["value"] * 100})
        if d["active"] and d["value"] > 0:
            used = self.cost(st["td"]) if d["unit"] == "PESO" else st["td"]
            res.append({"key": "daily", "period": calc.day_key(self.now), "used": used, "limit": d["value"], "unit": d["unit"],
                        "pct": used / d["value"] * 100})
        return res

    def save_limits(self, monthly, monthly_unit, daily, daily_unit, alerts_enabled=None):
        e, vals = {}, {}
        for key, text, unit in (("monthly", monthly, monthly_unit), ("daily", daily, daily_unit)):
            if unit not in ("KWH", "PESO"):
                unit = "PESO" if key == "monthly" else "KWH"
            if str(text or "").strip() == "":
                vals[key] = (unit, 0, 0)
                continue
            v = _num(text)
            if v is None or v <= 0:
                e[key] = "Enter an amount greater than 0, or leave it empty."
            else:
                vals[key] = (unit, v, 1)
        if e:
            raise ValidationError(e)
        for key, (unit, v, act) in vals.items():
            self.db.execute("INSERT INTO limits VALUES (?,?,?,?,?) ON CONFLICT(user_id,period) DO UPDATE SET "
                            "unit=excluded.unit, value=excluded.value, active=excluded.active", (self.uid, key, unit, v, act))
        if alerts_enabled is not None:
            self.db.execute("UPDATE users SET alerts_enabled=? WHERE id=?", (1 if alerts_enabled else 0, self.uid))
        self.db.commit()
        self.reload()
        self.check_all()

    # ---------------------------------------------------------------- forecast and tips
    def forecast(self):
        if self._fc is not None:
            return self._fc
        first = min((u["ts"] for u in self.usage), default=self.now)
        full = (calc.day_start(self.now) - calc.day_start(first)).days
        if full < 7:
            self._fc = {"ok": False, "need": 7 - full}
            return self._fc
        st = self.stats()
        fc = run_forecast(self.daily_series(min(full, 35)), calc.day_start(self.now), self.now, st["cycle"].end,
                          st["cyc"], self.temp_for)
        fc["projCost"] = self.cost(fc["projK"])
        self._fc = fc
        return fc

    def last_bill_check(self):
        if not self.bills:
            return None
        b = self.bills[0]
        start = datetime.fromisoformat(b["start"])
        end = datetime.fromisoformat(b["end"]) + DAY
        c = billcore.compare(b["kwh"], self.sum_kwh(start, end), b["amount"])
        c["bill"] = b
        return c

    def recommendations(self):
        st = self.stats()
        bc = self.last_bill_check()
        days_left = max(1, -(-(st["cycle"].end - self.now).total_seconds() // 86400))
        return recommendations(self.appliances, self.ranking(), st["cyc"], self.rate, int(days_left), self.forecast(),
                               self.limit_peso(), bill_gap=bc["gapK"] if bc else None, bill_id=bc["bill"]["id"] if bc else None,
                               day_key=calc.day_key(self.now), cycle_key=st["cycle"].key, feedback=self.feedback, now_ts=self.now)

    def set_tip_feedback(self, key, status):
        if status not in ("HELPFUL", "DISMISSED"):
            raise ValidationError({"status": "Status must be HELPFUL or DISMISSED."})
        self.db.execute("INSERT INTO tip_feedback VALUES (?,?,?,?) ON CONFLICT(user_id,key) DO UPDATE SET status=excluded.status, ts=excluded.ts",
                        (self.uid, key, status, ts(self.now)))
        self.db.commit()
        self.reload()

    # ---------------------------------------------------------------- usage plan
    def avg_daily_kwh(self, aid, days=14):
        t = calc.day_start(self.now)
        return self.sum_kwh(t - days * DAY, t, aid) / days

    def usage_plan(self):
        lp = self.limit_peso()
        if lp is None or self.rate <= 0:
            return None
        st = self.stats()
        today = calc.day_start(self.now)
        end = self.now + timedelta(seconds=1)
        return usage_plan(self.appliances, {a["id"]: self.avg_daily_kwh(a["id"]) for a in self.appliances},
                          {a["id"]: self.sum_kwh(today, end, a["id"]) for a in self.appliances}, lp / self.rate,
                          self.sum_kwh(st["cycle"].start, today), round((st["cycle"].end - today).days))

    def plan_item(self, aid):
        if not self.user["plan_active"]:
            return None
        p = self.usage_plan()
        if not p or not p["needed"]:
            return None
        return next((i for i in p["items"] if i["a"]["id"] == aid), None)

    def set_plan(self, active: bool):
        self.db.execute("UPDATE users SET plan_active=? WHERE id=?", (1 if active else 0, self.uid))
        self.db.commit()
        self.reload()
        self.check_all()

    # ---------------------------------------------------------------- checks (SRS 7.4.2)
    def check_all(self):
        """Offers the plan once per cycle; sends each 80%/100% alert once per period (BR-6);
        sends plan reminders for running timers once per appliance per day."""
        p = self.usage_plan()
        ck = self.cycle().key
        offered = self.db.execute("SELECT 1 FROM plan_offered WHERE user_id=? AND cycle_key=?", (self.uid, ck)).fetchone()
        if p and p["needed"] and not self.user["plan_active"] and not offered:
            fc = self.forecast()
            lp = self.limit_peso()
            pct = next((x["pct"] for x in self.limit_status() if x["key"] == "monthly"), 0)
            if pct >= 80 or (fc.get("ok") and fc["projCost"] > lp):
                self.db.execute("INSERT INTO plan_offered VALUES (?,?)", (self.uid, ck))
                self._notify("Usage plan ready", f"You are on track to go over {peso(lp)}. Open Save to turn on a daily allowance for each appliance.")
        for L in self.limit_status():
            for th in (80, 100):
                if L["pct"] < th:
                    continue
                sent = self.db.execute("SELECT 1 FROM alerts WHERE user_id=? AND period=? AND threshold=? AND period_key=?",
                                       (self.uid, L["key"], th, L["period"])).fetchone()
                if sent:
                    continue
                self.db.execute("INSERT INTO alerts(user_id,period,threshold,period_key,sent_at,amount,unit) VALUES (?,?,?,?,?,?,?)",
                                (self.uid, L["key"], th, L["period"], ts(self.now), L["limit"] * th / 100, L["unit"]))
                if self.user["alerts_enabled"]:
                    if th == 80:
                        self._notify(f"80% of your {L['key']} limit used",
                                     f"You have used {fmt_limit(L['used'], L['unit'])} of {fmt_limit(L['limit'], L['unit'])}.")
                    else:
                        self._notify("Monthly limit reached" if L["key"] == "monthly" else "Daily limit reached",
                                     f"You have used {fmt_limit(L['used'], L['unit'])} (limit {fmt_limit(L['limit'], L['unit'])}). "
                                     "Only essential appliances fit the plan now.")
        if self.user["plan_active"]:
            dk = calc.day_key(self.now)
            for a in self.appliances:
                if a["timer"] is None:
                    continue
                it = self.plan_item(a["id"])
                if not it:
                    continue
                row = self.db.execute("SELECT warn, over FROM plan_notes WHERE user_id=? AND day_key=? AND appliance_id=?",
                                      (self.uid, dk, a["id"])).fetchone()
                warn, over = (row["warn"], row["over"]) if row else (0, 0)
                if 0 < it["leftH"] <= 0.25 and not warn:
                    warn = 1
                    self._notify(f"15 minutes left for {a['type']}", f"Today's plan allows {fmt_h(it['allowH'])}. Plan to turn it off soon.")
                if it["leftH"] <= 0 and not over:
                    over = warn = 1
                    self._notify(f"Time to turn off the {a['type'].lower()}",
                                 f"Today's plan of {fmt_h(it['allowH'])} is used up. Stop the timer when you switch it off.")
                self.db.execute("INSERT INTO plan_notes VALUES (?,?,?,?,?) ON CONFLICT(user_id,day_key,appliance_id) DO UPDATE "
                                "SET warn=excluded.warn, over=excluded.over", (self.uid, dk, a["id"], warn, over))
        self.db.commit()
        self.alerts = [dict(r) for r in self.db.execute("SELECT * FROM alerts WHERE user_id=? ORDER BY sent_at DESC", (self.uid,))]

    # ---------------------------------------------------------------- settings
    def update_settings(self, rate, cycle_day):
        r, d = _num(rate), _num(cycle_day, int)
        e = {}
        if r is None or r <= 0:
            e["rate"] = "Enter a rate greater than 0."
        if d is None or not 1 <= d <= 31:
            e["cycle_day"] = "Choose a day from 1 to 31."
        if e:
            raise ValidationError(e)
        self.db.execute("UPDATE users SET rate=?, cycle_day=? WHERE id=?", (round(r, 2), d, self.uid))
        self.db.commit()
        self.reload()
        self.check_all()

    # ---------------------------------------------------------------- appliances (UC-02)
    @staticmethod
    def validate_appliance(f):
        e = {}
        if not (f.get("type") or "").strip():
            e["type"] = "Choose the appliance type."
        w = _num(f.get("watt"), int)
        if w is None or not 1 <= w <= 10000:
            e["watt"] = "Enter a wattage from 1 to 10,000 W."
        hs = str(f.get("hours") or "").strip()
        h = 0.0 if hs == "" else _num(hs)
        if h is None or not 0 <= h <= 24:
            e["hours"] = "Enter hours from 0 to 24."
        if e:
            raise ValidationError(e)
        return w, h

    def save_appliance(self, f, aid=None):
        w, h = self.validate_appliance(f)
        vals = (f["type"].strip(), (f.get("brand") or "").strip(), (f.get("model") or "").strip(), w,
                (f.get("location") or "").strip(), h, 1 if f.get("essential") in (True, "1", "on", "true", 1) else 0)
        if aid is None:
            cur = self.db.execute("INSERT INTO appliances(user_id,type,brand,model,watt,location,hours,essential) VALUES (?,?,?,?,?,?,?,?)",
                                  (self.uid, *vals))
            aid = cur.lastrowid
        else:
            self.appliance(aid)
            self.db.execute("UPDATE appliances SET type=?,brand=?,model=?,watt=?,location=?,hours=?,essential=? WHERE id=? AND user_id=?",
                            (*vals, aid, self.uid))
        self.db.commit()
        self.reload()
        self.check_all()
        return aid

    def delete_appliance(self, aid):
        a = self.appliance(aid)
        if a["timer"] is not None:
            self.stop_timer(aid)
        self.db.execute("UPDATE appliances SET deleted=1, timer_start=NULL WHERE id=? AND user_id=?", (a["id"], self.uid))
        self.db.commit()
        self.reload()

    # ---------------------------------------------------------------- timers and logging (UC-03)
    def start_timer(self, aid):
        a = self.appliance(aid)
        if a["timer"] is None:
            self.db.execute("UPDATE appliances SET timer_start=? WHERE id=?", (ts(self.now), a["id"]))
            self.db.commit()
            self.reload()
            self.check_all()

    def stop_timer(self, aid):
        a = self.appliance(aid)
        if a["timer"] is None:
            return 0.0
        total = 0.0
        for e, h in calc.split_by_day(a["timer"], self.now):
            self.db.execute("INSERT INTO usage(user_id,appliance_id,ts,hours,kwh,src) VALUES (?,?,?,?,?,?)",
                            (self.uid, a["id"], ts(e), round(h, 4), round(a["watt"] * h / 1000, 4), "TIMER"))
            total += h
        self.db.execute("UPDATE appliances SET timer_start=NULL WHERE id=?", (a["id"],))
        self.db.commit()
        self.reload()
        self.check_all()
        return total

    def logged_today(self, aid):
        t = calc.day_start(self.now)
        return any(u["a"] == aid and t <= u["ts"] <= self.now for u in self.usage)

    def log_hours(self, aid, hours_text, check=True):
        a = self.appliance(aid)
        h = _num(hours_text)
        if h is None or not 0 < h <= 24:
            raise ValidationError({"hours": "Enter hours from 0.1 to 24."})
        t = calc.day_start(self.now)
        already = self.sum_kwh(t, self.now + timedelta(seconds=1), a["id"]) / (a["watt"] / 1000)
        if already + h > 24.01:
            raise ValidationError({"hours": "That is more than 24 hours today for this appliance."})
        self.db.execute("INSERT INTO usage(user_id,appliance_id,ts,hours,kwh,src) VALUES (?,?,?,?,?,?)",
                        (self.uid, a["id"], ts(self.now), h, round(a["watt"] * h / 1000, 4), "LOGGED"))
        self.db.commit()
        self.reload()
        it = self.plan_item(a["id"])
        if it and it["leftH"] < 0:
            self._notify(f"{a['type']} is over today's plan", f"Plan: {fmt_h(it['allowH'])}, logged: {fmt_h(it['usedH'])}.")
        if check:
            self.check_all()

    def log_many(self, hours_by_id: dict):
        """'Log today's hours' sheet; empty entries are skipped. Returns errors by appliance id."""
        errors = {}
        for aid, text in hours_by_id.items():
            if str(text or "").strip() == "":
                continue
            try:
                self.log_hours(aid, text, check=False)
            except ValidationError as e:
                errors[str(aid)] = next(iter(e.errors.values()))
        self.check_all()
        return errors

    def recent_entries(self, aid, n=5):
        return sorted((u for u in self.usage if u["a"] == aid), key=lambda u: u["ts"], reverse=True)[:n]

    # ---------------------------------------------------------------- bills and meter (Feature 11)
    def add_bill(self, start, end, kwh, amount, src="MANUAL"):
        def d(x):
            if isinstance(x, date):
                return x
            try:
                return date.fromisoformat(str(x))
            except ValueError:
                return None
        s, e_, k, amt = d(start), d(end), _num(kwh), _num(amount)
        errs = billcore.validate_bill(s, e_, k, amt)
        if errs:
            raise ValidationError(errs)
        self.db.execute("INSERT INTO bills(user_id,start,end,kwh,amount,src,ts) VALUES (?,?,?,?,?,?,?)",
                        (self.uid, s.isoformat(), e_.isoformat(), k, amt, "SCAN" if src == "SCAN" else "MANUAL", ts(self.now)))
        self.db.commit()
        self.reload()

    def use_bill_rate(self):
        bc = self.last_bill_check()
        if not bc:
            raise ValidationError({"bill": "Add a bill first."})
        self.db.execute("UPDATE users SET rate=? WHERE id=?", (round(bc["eff"], 2), self.uid))
        self.db.commit()
        self.reload()
        self.check_all()

    def add_meter_reading(self, text):
        v = _num(text)
        if v is None or v <= 0:
            raise ValidationError({"reading": "Enter the number on your electric meter, in kWh."})
        if self.meter and v <= self.meter[-1]["reading"]:
            raise ValidationError({"reading": f"The reading must be higher than your last reading ({self.meter[-1]['reading']:,.1f})."})
        self.db.execute("INSERT INTO meter(user_id,ts,reading) VALUES (?,?,?)", (self.uid, ts(self.now), v))
        self.db.commit()
        self.reload()

    def meter_check(self):
        if len(self.meter) < 2:
            return None
        a, b = self.meter[-2], self.meter[-1]
        measured = b["reading"] - a["reading"]
        rec = self.sum_kwh(parse_ts(a["ts"]), parse_ts(b["ts"]))
        return {"a": a, "b": b, "measured": measured, "appK": rec, "gap": measured - rec,
                "coverage": rec / measured * 100 if measured > 0 else 0}

    # ---------------------------------------------------------------- what-if (Feature 12)
    def usual_hours(self):
        return {a["id"]: self.avg_daily_kwh(a["id"]) / (a["watt"] / 1000) for a in self.appliances}

    def what_if(self, changes, saving_pct=35, extra_cost=12000):
        return what_if(self.appliances, self.usual_hours(), changes, self.rate, saving_pct, extra_cost)

    # ---------------------------------------------------------------- notifications
    def notifications(self, mark_read=False):
        rows = [dict(r) for r in self.db.execute("SELECT * FROM notifications WHERE user_id=? ORDER BY id DESC", (self.uid,))]
        if mark_read:
            self.db.execute("UPDATE notifications SET read=1 WHERE user_id=?", (self.uid,))
            self.db.commit()
        return rows

    def unread(self):
        return self.db.execute("SELECT COUNT(*) c FROM notifications WHERE user_id=? AND read=0", (self.uid,)).fetchone()["c"]

    # ---------------------------------------------------------------- clock and demo controls
    def tick(self):
        """Real clock: run the checks (called by the app every minute)."""
        self.check_all()

    def advance(self, delta: timedelta):
        if not self.simulated:
            raise ValidationError({"clock": "Demo controls work only for the sample household."})
        end = self.now + delta
        while self.now < end:
            self.now = min(end, self.now + 15 * MIN)
            self.db.execute("UPDATE users SET clock=? WHERE id=?", (ts(self.now), self.uid))
            self.reload()
            self.check_all()
        self.db.commit()

    def demo_day(self):
        """The user logs usual hours for today's appliances without a running timer, then a day passes."""
        if not self.simulated:
            raise ValidationError({"clock": "Demo controls work only for the sample household."})
        ds = calc.day_start(self.now)
        for a in self.appliances:
            if a["timer"] is not None or a["hours"] <= 0:
                continue
            if any(u["a"] == a["id"] and ds <= u["ts"] < ds + DAY for u in self.usage):
                continue
            h = a["hours"]
            if re.search("air", a["type"], re.I):
                h = 7.4 + ((self.temp_for(ds) or 31) - 31) * 0.9
            it = self.plan_item(a["id"])
            if it:
                h = min(h, max(0, it["allowH"]))
            if h <= 0:
                continue
            self.db.execute("INSERT INTO usage(user_id,appliance_id,ts,hours,kwh,src) VALUES (?,?,?,?,?,?)",
                            (self.uid, a["id"], ts(ds + 21 * HOUR), round(h, 3), round(a["watt"] * h / 1000, 4), "LOGGED"))
        self.db.commit()
        self.reload()
        self.advance(ds + DAY + (self.now - ds) - self.now)

    def demo_use_up_to(self, pct):
        if not self.simulated:
            raise ValidationError({"clock": "Demo controls work only for the sample household."})
        L = next((x for x in self.limit_status() if x["key"] == "monthly"), None)
        if not L:
            raise ValidationError({"limit": "Set a monthly limit first."})
        target = L["limit"] * pct / 100 + 0.01
        if L["used"] >= target:
            raise ValidationError({"limit": f"This cycle is already at {round(L['pct'])}% of the limit."})
        need = (target - L["used"]) / (self.rate or 1) if L["unit"] == "PESO" else target - L["used"]
        a = next((x for x in self.appliances if not x["essential"]), None) or (self.appliances[0] if self.appliances else None)
        if a is None:
            raise ValidationError({"appliance": "Add an appliance first."})
        self.now = self.now + HOUR
        self.db.execute("UPDATE users SET clock=? WHERE id=?", (ts(self.now), self.uid))
        # Spread the extra use over the earlier days of this cycle, so no single day looks impossible.
        start = self.cycle().start
        days = [start + k * DAY + 20 * HOUR for k in range(max(1, (self.now.date() - start.date()).days))]
        days = [x for x in days if x < self.now] or [self.now]
        part = need / len(days)
        for when in days:
            self.db.execute("INSERT INTO usage(user_id,appliance_id,ts,hours,kwh,src) VALUES (?,?,?,?,?,?)",
                            (self.uid, a["id"], ts(when), round(part / (a["watt"] / 1000), 3), round(part, 4), "LOGGED"))
        self.db.commit()
        self.reload()
        self.check_all()

    def add_demo_meter_reading(self):
        """Demo: a meter reading now, 10% above the use recorded since the last reading."""
        last = self.meter[-1] if self.meter else {"reading": 15000.0, "ts": ts(self.now - 7 * DAY)}
        rec = self.sum_kwh(parse_ts(last["ts"]), self.now)
        self.add_meter_reading(f"{last['reading'] + max(1.0, rec * 1.1):.1f}")

    def export(self):
        return {"user": {"email": self.user["email"], "rate": self.rate, "cycleDay": self.user["cycle_day"]},
                "appliances": [{"type": a["type"], "watt": a["watt"], "hours": a["hours"], "essential": a["essential"]}
                               for a in self.appliances],
                "limits": {k: {"unit": v["unit"], "value": v["value"], "active": bool(v["active"])} for k, v in self.limits.items()},
                "records": len(self.usage), "bills": len(self.bills), "meterReadings": len(self.meter)}

    def delete_account(self):
        self.db.execute("DELETE FROM users WHERE id=?", (self.uid,))
        self.db.commit()
