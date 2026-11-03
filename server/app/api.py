"""REST API for the Flutter app (SRS 7.4.3). JSON in and out; every call except
register/login/demo needs `Authorization: Bearer <token>`."""
from __future__ import annotations

from datetime import timedelta
from functools import wraps

from flask import Blueprint, current_app, g, jsonify, request

from . import household as H
from . import views
from .core import bill as billcore
from .db import get_db
from .format import jsonable

bp = Blueprint("api", __name__, url_prefix="/api")


def ok(data=None, status=200):
    return jsonify(jsonable(data if data is not None else {"ok": True})), status


@bp.errorhandler(H.ValidationError)
def _validation(e):
    return jsonify({"error": "validation", "errors": e.errors}), 400


def auth(fn):
    @wraps(fn)
    def wrapper(*a, **kw):
        hdr = request.headers.get("Authorization", "")
        uid = H.user_for_token(get_db(), hdr[7:]) if hdr.startswith("Bearer ") else None
        if uid is None:
            return jsonify({"error": "unauthorized"}), 401
        g.house = H.Household(get_db(), uid)
        if not g.house.simulated and current_app.config["FETCH_WEATHER"]:
            g.house.refresh_weather()
        return fn(*a, **kw)
    return wrapper


def body():
    return request.get_json(silent=True) or {}


def with_new(data):
    """Adds the notifications created by this request, so the app can show them at once."""
    data = dict(data)
    data["newNotifications"] = g.house.new_notifications
    return data


# ---------------------------------------------------------------- accounts
@bp.get("/health")
def health():
    return ok({"status": "ok"})


@bp.post("/register")
def register():
    b = body()
    uid = H.create_account(get_db(), b.get("email"), b.get("password"), b.get("rate"), b.get("cycleDay", 1),
                           b.get("monthlyLimit", ""), b.get("consent", False))
    return ok({"token": H.issue_token(get_db(), uid)}, 201)


@bp.post("/login")
def login():
    b = body()
    uid = H.authenticate(get_db(), b.get("email"), b.get("password"))
    if uid is None:
        return jsonify({"error": "validation", "errors": {"password": "Incorrect email or password."}}), 401
    return ok({"token": H.issue_token(get_db(), uid)})


@bp.post("/demo")
def demo():
    """Creates a sample-household account and signs in (for demonstrations)."""
    uid = H.create_demo_user(get_db())
    return ok({"token": H.issue_token(get_db(), uid)}, 201)


@bp.get("/me")
@auth
def me():
    return ok(views.meta(g.house))


@bp.put("/settings")
@auth
def settings():
    b = body()
    g.house.update_settings(b.get("rate"), b.get("cycleDay"))
    return ok(with_new(views.meta(g.house)))


@bp.get("/limits")
@auth
def get_limits():
    return ok(views.limits(g.house))


@bp.put("/limits")
@auth
def put_limits():
    b = body()
    g.house.save_limits(b.get("monthly", ""), b.get("monthlyUnit", "PESO"), b.get("daily", ""), b.get("dailyUnit", "KWH"),
                        b.get("alertsEnabled"))
    return ok(with_new(views.limits(g.house)))


@bp.get("/export")
@auth
def export():
    return ok(g.house.export())


@bp.delete("/account")
@auth
def delete_account():
    g.house.delete_account()
    return ok()


# ---------------------------------------------------------------- screens
@bp.get("/dashboard")
@auth
def dashboard():
    return ok(views.home(g.house))


@bp.post("/tick")
@auth
def tick():
    g.house.tick()
    return ok(with_new(views.meta(g.house)))


@bp.get("/notifications")
@auth
def notifications():
    return ok({"notifications": g.house.notifications(mark_read=request.args.get("markRead") == "1")})


@bp.get("/usage")
@auth
def usage():
    return ok(views.usage(g.house, request.args.get("view", "daily")))


@bp.get("/save")
@auth
def save():
    return ok(views.save(g.house))


@bp.get("/check")
@auth
def check():
    return ok(views.check(g.house))


# ---------------------------------------------------------------- appliances, timers, logging
@bp.get("/appliances")
@auth
def list_appliances():
    return ok(views.appliances(g.house))


@bp.post("/appliances")
@auth
def add_appliance():
    aid = g.house.save_appliance(body())
    return ok(with_new(views.appliance_detail(g.house, aid)), 201)


@bp.get("/appliances/<int:aid>")
@auth
def get_appliance(aid):
    return ok(views.appliance_detail(g.house, aid))


@bp.put("/appliances/<int:aid>")
@auth
def put_appliance(aid):
    g.house.save_appliance(body(), aid)
    return ok(with_new(views.appliance_detail(g.house, aid)))


@bp.delete("/appliances/<int:aid>")
@auth
def delete_appliance(aid):
    g.house.delete_appliance(aid)
    return ok()


@bp.post("/appliances/<int:aid>/start")
@auth
def start(aid):
    g.house.start_timer(aid)
    return ok(with_new(views.appliance_detail(g.house, aid)))


@bp.post("/appliances/<int:aid>/stop")
@auth
def stop(aid):
    hrs = g.house.stop_timer(aid)
    data = with_new(views.appliance_detail(g.house, aid))
    data["recordedHours"] = hrs
    return ok(data)


@bp.post("/appliances/<int:aid>/log")
@auth
def log(aid):
    g.house.log_hours(aid, body().get("hours"))
    return ok(with_new(views.appliance_detail(g.house, aid)))


@bp.post("/log")
@auth
def log_many():
    errors = g.house.log_many(body().get("hours") or {})
    data = with_new(views.appliances(g.house))
    data["errors"] = errors
    return ok(data, 400 if errors else 200)


# ---------------------------------------------------------------- plan, tips, what-if
@bp.post("/plan")
@auth
def plan():
    g.house.set_plan(bool(body().get("active")))
    return ok(with_new(views.save(g.house)))


@bp.post("/tips/<path:key>")
@auth
def tip(key):
    g.house.set_tip_feedback(key, body().get("status", "").upper())
    return ok(views.save(g.house))


@bp.get("/whatif")
@auth
def whatif_get():
    return ok(views.what_if(g.house))


@bp.post("/whatif")
@auth
def whatif_post():
    b = body()
    changes = {int(k): {"dh": float(v.get("dh", 0)), "inv": bool(v.get("inv"))} for k, v in (b.get("changes") or {}).items()}
    saving, extra = float(b.get("savingPct", 35)), float(b.get("extraCost", 12000))
    r = g.house.what_if(changes, saving, extra)
    return ok(views.what_if(g.house, r, changes, saving, extra))


# ---------------------------------------------------------------- bills and meter
@bp.post("/bills/parse")
@auth
def parse_bill():
    """The phone reads the photo with ML Kit and sends the text; the server finds the values."""
    f = billcore.parse_bill_text(body().get("text", ""))
    return ok(f)


@bp.post("/bills")
@auth
def add_bill():
    b = body()
    g.house.add_bill(b.get("start"), b.get("end"), b.get("kwh"), b.get("amount"), b.get("src", "MANUAL"))
    return ok(views.check(g.house), 201)


@bp.post("/bills/use-rate")
@auth
def use_rate():
    g.house.use_bill_rate()
    return ok(with_new(views.check(g.house)))


@bp.post("/meter")
@auth
def meter():
    g.house.add_meter_reading(body().get("reading"))
    return ok(views.check(g.house), 201)


# ---------------------------------------------------------------- demo controls (sample household only)
@bp.post("/demo/advance")
@auth
def demo_advance():
    b = body()
    g.house.advance(timedelta(hours=float(b.get("hours", 1))))
    return ok(with_new(views.meta(g.house)))


@bp.post("/demo/day")
@auth
def demo_day():
    g.house.demo_day()
    return ok(with_new(views.meta(g.house)))


@bp.post("/demo/use")
@auth
def demo_use():
    g.house.demo_use_up_to(int(body().get("pct", 80)))
    return ok(with_new(views.meta(g.house)))


@bp.post("/demo/meter")
@auth
def demo_meter():
    g.house.add_demo_meter_reading()
    return ok(views.check(g.house))


@bp.post("/demo/reset")
@auth
def demo_reset():
    H.load_sample(get_db(), g.house.uid)
    return ok({"ok": True})
