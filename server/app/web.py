"""Web pages: the same features as the Flutter app, rendered by Flask for demonstrations.
Every page reads its data from views.py, the same functions the REST API uses."""
from __future__ import annotations

import os
import tempfile
from datetime import timedelta
from functools import wraps

from flask import (Blueprint, current_app, flash, g, redirect, render_template, request, session, url_for)

from . import household as H
from . import views
from .core import bill as billcore
from .db import get_db

bp = Blueprint("web", __name__)

SAMPLE_BILL_TEXT = """ALBAY ELECTRIC COOPERATIVE
STATEMENT OF ACCOUNT
Account: 0123-4567-89   Residential
Billing period: Sep 21 - Oct 20, 2026
Present reading: 15,559   Previous: 15,230
KWH USED 329
Total amount due: 4,309.90"""


def login_required(fn):
    @wraps(fn)
    def wrapper(*a, **kw):
        uid = session.get("uid")
        if uid is None:
            return redirect(url_for("web.index"))
        try:
            g.house = H.Household(get_db(), uid, notify=lambda n: session.setdefault("toasts", []).append(
                {"title": n["title"], "body": n["body"]}))
        except KeyError:
            session.clear()
            return redirect(url_for("web.index"))
        if not g.house.simulated and current_app.config["FETCH_WEATHER"]:
            g.house.refresh_weather()
        return fn(*a, **kw)
    return wrapper


def page(template, tab=None, **data):
    toasts = session.pop("toasts", [])
    return render_template(template, tab=tab, toasts=toasts, h=g.house, **data)


def errors_flash(e: H.ValidationError):
    for msg in e.errors.values():
        flash(msg, "error")


def back(default="web.home"):
    return redirect(request.form.get("next") or request.referrer or url_for(default))


# ---------------------------------------------------------------- landing and accounts
@bp.get("/")
def index():
    if session.get("uid"):
        return redirect(url_for("web.home"))
    return render_template("landing.html")


@bp.post("/demo")
def demo():
    session.clear()
    session["uid"] = H.create_demo_user(get_db())
    return redirect(url_for("web.home"))


@bp.route("/login", methods=["GET", "POST"])
def login():
    err = None
    if request.method == "POST":
        uid = H.authenticate(get_db(), request.form.get("email"), request.form.get("password"))
        if uid:
            session.clear()
            session["uid"] = uid
            return redirect(url_for("web.home"))
        err = "Incorrect email or password."
    return render_template("login.html", err=err)


@bp.route("/register", methods=["GET", "POST"])
def register():
    errors, form = {}, request.form
    if request.method == "POST":
        try:
            uid = H.create_account(get_db(), form.get("email"), form.get("password"), form.get("rate"), form.get("cycle_day"),
                                   form.get("limit"), form.get("consent") == "on")
            session.clear()
            session["uid"] = uid
            return redirect(url_for("web.home"))
        except H.ValidationError as e:
            errors = e.errors
    return render_template("register.html", errors=errors, form=form)


@bp.post("/logout")
def logout():
    session.clear()
    return redirect(url_for("web.index"))


# ---------------------------------------------------------------- tabs
@bp.get("/home")
@login_required
def home():
    return page("home.html", "home", d=views.home(g.house))


@bp.get("/appliances")
@login_required
def appliances():
    return page("appliances.html", "appliances", d=views.appliances(g.house))


@bp.get("/usage")
@login_required
def usage():
    return page("usage.html", "usage", d=views.usage(g.house, request.args.get("view", "daily")))


@bp.get("/save")
@login_required
def save():
    return page("save.html", "save", d=views.save(g.house))


@bp.get("/check")
@login_required
def check():
    return page("check.html", "check", d=views.check(g.house))


# ---------------------------------------------------------------- appliances
@bp.route("/appliances/new", methods=["GET", "POST"])
@login_required
def appliance_new():
    errors, form = {}, request.form
    if request.method == "POST":
        try:
            aid = g.house.save_appliance(form.to_dict())
            flash("Appliance saved.", "ok")
            return redirect(url_for("web.appliance", aid=aid))
        except H.ValidationError as e:
            errors = e.errors
    return page("appliance_form.html", "appliances", errors=errors, form=form, types=H.APPLIANCE_TYPES, editing=None)


@bp.route("/appliances/<int:aid>/edit", methods=["GET", "POST"])
@login_required
def appliance_edit(aid):
    a = g.house.appliance(aid)
    errors, form = {}, request.form if request.method == "POST" else {**a, "essential": "on" if a["essential"] else ""}
    if request.method == "POST":
        try:
            g.house.save_appliance(request.form.to_dict(), aid)
            flash("Changes saved.", "ok")
            return redirect(url_for("web.appliance", aid=aid))
        except H.ValidationError as e:
            errors = e.errors
    return page("appliance_form.html", "appliances", errors=errors, form=form, types=H.APPLIANCE_TYPES, editing=a)


@bp.get("/appliances/<int:aid>")
@login_required
def appliance(aid):
    try:
        d = views.appliance_detail(g.house, aid)
    except H.ValidationError:
        return redirect(url_for("web.appliances"))
    return page("appliance.html", "appliances", d=d)


@bp.post("/appliances/<int:aid>/<action>")
@login_required
def appliance_action(aid, action):
    try:
        if action == "start":
            g.house.start_timer(aid)
        elif action == "stop":
            hrs = g.house.stop_timer(aid)
            flash(f"Recorded {hrs:.2f} hours.", "ok")
        elif action == "log":
            g.house.log_hours(aid, request.form.get("hours"))
            flash("Hours logged.", "ok")
        elif action == "delete":
            g.house.delete_appliance(aid)
            flash("Appliance deleted. Its past usage stays in your totals.", "ok")
            return redirect(url_for("web.appliances"))
    except H.ValidationError as e:
        errors_flash(e)
    return back("web.appliances")


@bp.route("/log", methods=["GET", "POST"])
@login_required
def log_sheet():
    errors = {}
    if request.method == "POST":
        entries = {k[2:]: v for k, v in request.form.items() if k.startswith("h_")}
        errors = g.house.log_many(entries)
        if not errors:
            flash("Hours saved.", "ok")
            return redirect(url_for("web.home"))
    return page("log.html", "home", d=views.appliances(g.house), errors=errors)


# ---------------------------------------------------------------- plan, tips, what-if
@bp.post("/plan")
@login_required
def plan():
    g.house.set_plan(request.form.get("active") == "1")
    return back("web.save")


@bp.post("/tips")
@login_required
def tip():
    g.house.set_tip_feedback(request.form["key"], request.form["status"])
    return back("web.save")


@bp.route("/whatif", methods=["GET", "POST"])
@login_required
def whatif():
    changes, saving, extra, result = {}, 35.0, 12000.0, None
    if request.method == "POST":
        for a in g.house.appliances:
            dh = request.form.get(f"dh_{a['id']}")
            inv = request.form.get(f"inv_{a['id']}") == "on"
            if dh is not None:
                changes[a["id"]] = {"dh": float(dh or 0), "inv": inv}
        saving = float(request.form.get("saving") or 35)
        extra = float((request.form.get("extra") or "12000").replace(",", ""))
    result = g.house.what_if(changes, saving, extra)
    return page("whatif.html", "save", d=views.what_if(g.house, result, changes, saving, extra))


# ---------------------------------------------------------------- bills and meter
@bp.route("/bills/new", methods=["GET", "POST"])
@login_required
def bill_new():
    errors, fields, scan_msg, text = {}, {}, None, ""
    if request.method == "POST":
        act = request.form.get("act")
        if act in ("sample", "read", "photo"):
            if act == "photo" and request.files.get("photo") and request.files["photo"].filename:
                f = request.files["photo"]
                tmp = tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(f.filename)[1])
                f.save(tmp.name)
                tmp.close()
                text = billcore.ocr_image(tmp.name) or ""
                os.unlink(tmp.name)
                if not text:
                    scan_msg = "Could not read the photo on this server (Tesseract not installed). Paste the text or type the values."
            else:
                text = SAMPLE_BILL_TEXT if act == "sample" else request.form.get("text", "")
            p = billcore.parse_bill_text(text)
            fields = {"start": p["start"].isoformat() if p["start"] else "", "end": p["end"].isoformat() if p["end"] else "",
                      "kwh": f"{p['kwh']:g}" if p["kwh"] else "", "amount": f"{p['amount']:.2f}" if p["amount"] else "",
                      "src": "SCAN"}
            if not scan_msg:
                found = sum(1 for k in ("start", "kwh", "amount") if fields[k])
                scan_msg = ("Text found on the photo. Check the values below before saving." if found == 3
                            else "Some values could not be read. Please fill them in.")
        else:
            fields = request.form.to_dict()
            try:
                g.house.add_bill(fields.get("start"), fields.get("end"), fields.get("kwh"), fields.get("amount"), fields.get("src", "MANUAL"))
                flash("Bill saved and compared.", "ok")
                return redirect(url_for("web.check"))
            except H.ValidationError as e:
                errors = e.errors
    return page("bill_form.html", "check", errors=errors, f=fields, scan_msg=scan_msg, text=text)


@bp.post("/bills/use-rate")
@login_required
def use_rate():
    try:
        g.house.use_bill_rate()
        flash(f"Your rate is now ₱{g.house.rate:.2f} per kWh.", "ok")
    except H.ValidationError as e:
        errors_flash(e)
    return redirect(url_for("web.check"))


@bp.post("/meter")
@login_required
def meter():
    try:
        g.house.add_meter_reading(request.form.get("reading"))
        flash("Meter reading saved.", "ok")
    except H.ValidationError as e:
        errors_flash(e)
    return redirect(url_for("web.check"))


# ---------------------------------------------------------------- settings
@bp.route("/settings", methods=["GET", "POST"])
@login_required
def settings():
    errors = {}
    if request.method == "POST":
        try:
            g.house.update_settings(request.form.get("rate"), request.form.get("cycle_day"))
            flash("Settings saved.", "ok")
            return redirect(url_for("web.settings"))
        except H.ValidationError as e:
            errors = e.errors
    return page("settings.html", None, errors=errors)


@bp.route("/limits", methods=["GET", "POST"])
@login_required
def limits():
    errors = {}
    if request.method == "POST":
        f = request.form
        try:
            g.house.save_limits(f.get("monthly"), f.get("monthly_unit"), f.get("daily"), f.get("daily_unit"), f.get("alerts") == "on")
            flash("Limits saved.", "ok")
            return redirect(url_for("web.limits"))
        except H.ValidationError as e:
            errors = e.errors
    return page("limits.html", None, d=views.limits(g.house), errors=errors)


@bp.get("/notifications")
@login_required
def notifications():
    return page("notifications.html", None, items=g.house.notifications(mark_read=True))


@bp.get("/help")
@login_required
def help_page():
    return page("help.html", None)


@bp.route("/data", methods=["GET", "POST"])
@login_required
def data():
    if request.method == "POST":
        g.house.delete_account()
        session.clear()
        return redirect(url_for("web.index"))
    return page("data.html", None, export=g.house.export())


# ---------------------------------------------------------------- demo controls
@bp.post("/demo/<action>")
@login_required
def demo_action(action):
    try:
        if action == "hour":
            g.house.advance(timedelta(hours=1))
        elif action == "day":
            g.house.demo_day()
        elif action in ("use80", "use100"):
            g.house.demo_use_up_to(80 if action == "use80" else 100)
        elif action == "meter":
            g.house.add_demo_meter_reading()
        elif action == "reset":
            H.load_sample(get_db(), g.house.uid)
        elif action == "new":
            session.clear()
            return redirect(url_for("web.register"))
    except H.ValidationError as e:
        errors_flash(e)
    return back()
