"""Acceptance tests (SRS 5.2.6) run in a real browser against the running Flask server.

    python run.py            # in one terminal (or set BASE_URL)
    python acceptance/run_acceptance.py

Writes acceptance/results.json and screenshots in acceptance/shots/.
"""
import json
import os
import re
import sys

from playwright.sync_api import sync_playwright

BASE = os.environ.get("BASE_URL", "http://localhost:5000")
# Windows terminals may not use UTF-8; keep "₱" and "°" from crashing the output.
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
HERE = os.path.dirname(os.path.abspath(__file__))
SHOTS = os.path.join(HERE, "shots")
os.makedirs(SHOTS, exist_ok=True)
results = []


def check(tid, story, criterion, ok, detail=""):
    results.append({"id": tid, "story": story, "criterion": criterion, "pass": bool(ok), "detail": str(detail)[:300]})
    print(("PASS " if ok else "FAIL ") + tid + " " + criterion + ("" if ok else "  →  " + str(detail)[:200]))


def text(pg):
    # Open every "How is this calculated?" section, as a user would tap it, then read the screen.
    pg.evaluate("document.querySelectorAll('.content details').forEach(d => d.open = true)")
    return pg.locator(".content").inner_text()


def shot(pg, name, scroll=None):
    if scroll is not None:
        pg.evaluate(f"document.querySelector('.content').scrollTop = {scroll}")
    pg.locator(".phone").screenshot(path=os.path.join(SHOTS, name + ".png"))


def post_demo(pg, label):
    pg.get_by_role("button", name=label, exact=True).click()
    pg.wait_for_load_state()


def main():
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={"width": 1280, "height": 900}, device_scale_factor=2)
        errors = []
        pg.on("pageerror", lambda e: errors.append(str(e)))

        # ---------------- Feature 1: account (US-01, US-02)
        pg.goto(BASE + "/register")
        pg.get_by_role("button", name="Create account").click()
        t = pg.locator("main").inner_text()
        check("T01", "US-01", "Missing email, short password, rate 0 and no consent are rejected with messages",
              all(m in t for m in ["Enter a valid email address.", "Use at least 8 characters.", "Enter a rate greater than 0.",
                                   "Please agree to the Privacy Notice"]), t)
        pg.screenshot(path=os.path.join(SHOTS, "01_register_errors.png"), full_page=True)
        email = f"tester{os.getpid()}@example.com"
        pg.fill("input[name=email]", email)
        pg.fill("input[name=password]", "longenough1")
        pg.fill("input[name=rate]", "12.50")
        pg.select_option("select[name=cycle_day]", "21")
        pg.fill("input[name=limit]", "3000")
        pg.check("input[name=consent]")
        pg.get_by_role("button", name="Create account").click()
        check("T02", "US-01", "Valid email, 8+ character password, rate and consent create the account and open Home",
              pg.url.endswith("/home") and "Home" in pg.locator("h1").inner_text(), pg.url)
        pg.goto(BASE + "/save")
        check("T03", "US-11", "A new user without 7 days of data sees how many days are needed",
              "7 more days of records" in text(pg), text(pg)[:200])
        pg.goto(BASE + "/settings")
        pg.fill("input[name=rate]", "0")
        pg.get_by_role("button", name="Save", exact=True).click()
        check("T04", "US-02", "Rate 0 is rejected", "Enter a rate greater than 0." in text(pg))
        pg.fill("input[name=rate]", "12.50")
        pg.get_by_role("button", name="Save", exact=True).click()
        check("T05", "US-02", "Rate 12.50 is saved", "Settings saved." in text(pg) and pg.input_value("input[name=rate]") == "12.50")
        pg.get_by_role("button", name="Sign out").click()
        pg.goto(BASE + "/login")
        pg.fill("input[name=email]", email)
        pg.fill("input[name=password]", "wrongpassword")
        pg.get_by_role("button", name="Sign in").click()
        check("T06", "US-01", "A wrong password shows \"Incorrect email or password.\"", "Incorrect email or password." in pg.content())

        # ---------------- sample household
        pg.goto(BASE + "/")
        pg.get_by_role("button", name="Open sample household").click()
        t = text(pg)
        check("T07", "US-05", "Home shows each running timer with its elapsed time", "Electric fan" in t and "1 h 10 min" in t, t[:200])
        check("T08", "US-07", "Home shows today's and the cycle's kWh with peso estimates",
              "6.57 kWh" in t and "119.3 kWh" in t and "₱1,491.86" in t, t[:400])
        check("T09", "US-10", "Monthly limit bar shows 37% and the forecast is above the ₱4,000.00 limit",
              "37%" in t and "₱4,068.37" in t and "Above limit" in t, t)
        shot(pg, "02_home")

        # ---------------- Feature 2: appliances (US-03, US-04)
        pg.goto(BASE + "/appliances")
        shot(pg, "03_appliances")
        pg.goto(BASE + "/appliances/new")
        pg.select_option("select[name=type]", "Other")
        pg.fill("input[name=watt]", "0")
        pg.get_by_role("button", name="Save appliance").click()
        check("T10", "US-03", "Wattage 0 is rejected with the 1–10,000 W message", "Enter a wattage from 1 to 10,000 W." in text(pg))
        shot(pg, "04_add_error")
        pg.fill("input[name=watt]", "20000")
        pg.get_by_role("button", name="Save appliance").click()
        check("T11", "US-03", "Wattage 20,000 is rejected", "Enter a wattage from 1 to 10,000 W." in text(pg))
        pg.fill("input[name=watt]", "1000")
        pg.get_by_role("button", name="Save appliance").click()
        check("T12", "US-03", "Valid appliance (Other, 1,000 W) is saved", "Appliance saved." in text(pg) and "1,000 W" in text(pg))
        new_url = pg.url
        before = pg.evaluate("fetch('/usage').then(r=>r.text())")
        cyc_before = re.search(r"\(([\d,.]+) kWh ÷", before).group(1)
        pg.goto(BASE + "/appliances")
        pg.click("text=Television")
        tv_url = pg.url
        pg.goto(new_url)
        pg.locator("input[name=hours]").fill("3")
        pg.get_by_role("button", name="Log", exact=True).click()
        pg.goto(new_url + "/edit")
        pg.on("dialog", lambda d: d.accept())
        pg.get_by_role("button", name="Delete appliance").click()
        after = pg.evaluate("fetch('/usage').then(r=>r.text())")
        cyc_after = re.search(r"\(([\d,.]+) kWh ÷", after).group(1)
        check("T13", "US-04", "A deleted appliance leaves the list but its usage stays in the cycle total",
              "Other" not in text(pg) and float(cyc_after.replace(",", "")) > float(cyc_before.replace(",", "")),
              f"{cyc_before} → {cyc_after}")

        # ---------------- Feature 3: timers and logging (US-05, US-06)
        pg.goto(tv_url)
        pg.get_by_role("button", name="Start").click()
        check("T14", "US-05", "Start shows the timer as running", "timer running since 9:40 am" in text(pg).lower(), text(pg)[:200])
        shot(pg, "05_tv_timer")
        post_demo(pg, "+1 hour")
        post_demo(pg, "+1 hour")
        pg.get_by_role("button", name="Stop").click()
        t = text(pg)
        check("T15", "US-05", "Stop after 2 hours saves 120 W × 2 h = 0.24 kWh labeled Timer",
              "Recorded 2.00 hours." in t and "2 h · 0.24 kWh" in t and "Timer" in t, t)
        pg.locator("input[name=hours]").fill("30")
        pg.get_by_role("button", name="Log", exact=True).click()
        check("T16", "US-06", "Hours outside 0.1–24 are rejected", "Enter hours from 0.1 to 24." in text(pg))
        pg.locator("input[name=hours]").fill("1")
        pg.get_by_role("button", name="Log", exact=True).click()
        check("T17", "US-06", "Logging 1 h for a 120 W television saves 0.12 kWh labeled Logged",
              "Hours logged." in text(pg) and "1 h · 0.12 kWh" in text(pg) and "Logged" in text(pg), text(pg))
        pg.goto(BASE + "/log")
        t = text(pg)
        check("T18", "US-06", "Log-today screen skips appliances with a running timer and shows usual hours as hints",
              "Electric fan" not in t and "Air conditioner" in t and pg.locator("input[placeholder='8 h']").count() >= 1, t[:300])
        shot(pg, "06_log_sheet")
        pg.locator("input[name^=h_]").first.fill("25")
        pg.get_by_role("button", name="Save hours").click()
        check("T19", "US-06", "An invalid entry on the log sheet shows its error", "Enter hours from 0.1 to 24." in text(pg) or "more than 24 hours" in text(pg), text(pg)[:300])

        # ---------------- Features 4–6: usage, costs, ranking
        pg.goto(BASE + "/usage")
        t = text(pg)
        check("T20", "US-07", "Daily view shows the last 7 days and Today", "Today" in pg.inner_html(".content") and "last 7 days" in t.lower())
        check("T21", "US-08", "Projection formula (cycle kWh ÷ days) × days in cycle × rate is shown", "÷ 11 days) × 31 days × ₱12.50" in t, t)
        shot(pg, "07_usage_daily")
        check("T22", "US-09", "Appliances ranked by share; air conditioner flagged \"Above usual\"",
              t.index("Air conditioner") < t.index("Refrigerator") and "Above usual" in t, t)
        shot(pg, "08_usage_share", scroll=400)
        pg.goto(BASE + "/usage?view=monthly")
        check("T23", "US-07", "Monthly view shows billing cycles", "past months" in text(pg).lower() and "This cycle" in pg.inner_html(".content"))
        shot(pg, "09_usage_monthly")

        # ---------------- Feature 8–9: forecast and tips
        pg.goto(BASE + "/save")
        t = text(pg)
        check("T24", "US-11", "A 7-day forecast and the projected cycle total are shown", "next 7 days" in t.lower() and re.search(r"expected bill this month\s+₱[\d,]+\.\d\d", t, re.I) and re.search(r"forecast [\d,.]+ kWh for the month", t, re.I), t[:300])
        check("T25", "US-15", "The forecast uses the daily high: weather model, °C per day, and kWh per 1°C",
              "Weather-aware regression" in t and "34°" in pg.inner_html(".content") and "each 1°C hotter adds about 0.8 kWh" in t, t[:400])
        shot(pg, "10_save_forecast")
        check("T26", "US-12", "Air-conditioner tip shows about 30 kWh (₱375.00)", "Air conditioner: use it 1 hour less per day" in t and "₱375.00" in t)
        check("T27", "US-16", "A tip points to usage missing from the last bill", "your last bill shows but the app did not record" in t)
        shot(pg, "11_save_plan_tips", scroll=520)
        card = pg.locator(".card", has=pg.get_by_role("button", name="Dismiss")).last
        title = card.locator(".lead").inner_text()
        card.get_by_role("button", name="Dismiss").click()
        check("T28", "US-12", "Dismissed tip is hidden", title not in text(pg), title)

        # ---------------- Feature 7 and 10: alerts, plan, reminders
        post_demo(pg, "Use up to 80% of limit")
        toasts = pg.locator("#toasts").inner_text() if pg.locator("#toasts").count() else ""
        check("T29", "US-10", "Reaching 80% of the ₱4,000 limit sends a warning notification", "80% of your monthly limit used" in toasts, toasts)
        n_text = pg.evaluate("fetch('/notifications').then(r=>r.text())")
        check("T30", "US-13", "When heading over the limit, the app offers a usage plan once per cycle",
              n_text.count("Usage plan ready") == 1, n_text.count("Usage plan ready"))
        pg.goto(BASE + "/home")
        shot(pg, "12_alert80")
        pg.goto(BASE + "/save")
        text(pg)  # opens "How is this calculated?"
        p_text = pg.locator("#plan").inner_text()
        check("T31", "US-13", "Plan: allowances below usual hours; the essential refrigerator is not listed",
              "Air conditioner" in p_text and "Refrigerator" not in p_text and "→" in p_text, p_text)
        pg.get_by_role("button", name="Turn on plan and reminders").click()
        check("T32", "US-13", "Turning on the plan shows hours used against each allowance", "used" in pg.locator("#plan").inner_text())
        shot(pg, "13_plan_on", scroll=300)
        # Reminders: fresh sample household, plan on, the fan timer keeps running (allowance about 6 h 47 min)
        post_demo(pg, "Reload sample household")
        pg.goto(BASE + "/save")
        pg.get_by_role("button", name="Turn on plan and reminders").click()
        seen15 = seen_off = False
        for _ in range(8):
            post_demo(pg, "+1 hour")
            tt = pg.locator("#toasts").inner_text() if pg.locator("#toasts").count() else ""
            if "15 minutes left for Electric fan" in tt and not seen15:
                seen15 = True
                shot(pg, "14_reminder_15min")
            if "Time to turn off the electric fan" in tt and not seen_off:
                seen_off = True
                shot(pg, "15_reminder_over")
        check("T33", "US-14", "A running timer gets a reminder 15 minutes before today's allowance", seen15)
        check("T34", "US-14", "A reminder to turn it off is sent when the allowance is used up", seen_off)
        pg.goto(BASE + "/notifications")
        t = text(pg)
        check("T35", "US-14", "Each reminder is sent once per appliance per day",
              t.count("Time to turn off the electric fan") == 1 and t.count("15 minutes left for Electric fan") == 1, t)
        shot(pg, "16_notifications")
        post_demo(pg, "Reach 100% of limit")
        pg.goto(BASE + "/limits")
        t = text(pg)
        check("T36", "US-10", "Reaching 100% is recorded in the alert history with the 80% warning",
              "Limit reached (100%, monthly)" in t and "Warning (80%, monthly)" in t, t)
        shot(pg, "17_limits")

        pg.get_by_role("button", name="Reload sample household").click()
        # ---------------- Feature 12: what-if
        pg.goto(BASE + "/whatif")
        sl = pg.locator("input[type=range]").first
        with pg.expect_navigation():
            sl.evaluate("e => { e.value = -1; e.form.submit(); }")
        check("T44", "US-18", "Air conditioner 1 hour less a day = −₱375.00 a month (at ₱12.50)",
              "₱375.00" in pg.locator("#wi-peso").inner_text() and "You would save each month" in text(pg),
              pg.locator("#wi-peso").inner_text())
        shot(pg, "20_whatif")
        with pg.expect_navigation():
            pg.locator("input[name^=inv_]").first.check()
        check("T45", "US-18", "Inverter option shows the payback period", "pays for itself in about" in text(pg))

        # ---------------- Feature 11: Bill Check and meter
        pg.goto(BASE + "/check")
        t = text(pg)
        check("T37", "US-16", "Bill Check shows the bill vs recorded kWh, 88% coverage, and the all-in rate",
              "The app recorded 88% of your bill" in t and "329 kWh" in t and "₱13.10/kWh" in t, t[:500])
        shot(pg, "18_check")
        pg.goto(BASE + "/bills/new")
        pg.get_by_role("button", name="Use sample bill photo").click()
        ok = pg.input_value("input[name=kwh]") == "329" and pg.input_value("input[name=amount]") == "4309.90" and pg.input_value("input[name=start]") == "2026-09-21"
        check("T38", "US-16", "Scanning the sample bill fills the period, kWh, and amount for the user to confirm", ok)
        shot(pg, "19_bill_scan", scroll=300)
        pg.fill("input[name=kwh]", "0")
        pg.get_by_role("button", name="Save and compare").click()
        check("T39", "US-16", "A bill with 0 kWh is rejected", "Enter the kWh used, greater than 0." in text(pg))
        pg.fill("input[name=kwh]", "329")
        pg.get_by_role("button", name="Save and compare").click()
        check("T40", "US-16", "A saved bill is compared on the Check screen", "Bill saved and compared." in text(pg))
        pg.get_by_role("button", name="Use ₱13.10 as my rate").click()
        check("T41", "US-16", "The bill's all-in rate can be set as the app's rate", "Your rate is now ₱13.10 per kWh." in text(pg))
        pg.fill("input[name=reading]", "100")
        pg.get_by_role("button", name="Save", exact=True).click()
        check("T42", "US-17", "A meter reading lower than the last one is rejected", "must be higher than your last reading" in text(pg))
        post_demo(pg, "Add a meter reading now")
        check("T43", "US-17", "Two readings show the measured use next to what the app recorded", "(meter)" in text(pg) and "Recorded in the app" in text(pg))

        # ---------------- general
        pg.set_viewport_size({"width": 400, "height": 860})
        pg.goto(BASE + "/home")
        sw = pg.evaluate("document.documentElement.scrollWidth")
        check("T46", "NFR-ACC", "No horizontal scrolling at 400 px phone width", sw <= 400, sw)
        hs = pg.evaluate("[...document.querySelectorAll('.screen .btn, .screen .nav a, .screen .iconbtn')].map(e=>e.getBoundingClientRect().height).filter(h=>h>0)")
        check("T47", "NFR-ACC-3", "Buttons in the app are at least 40 px tall", min(hs) >= 40, min(hs))
        check("T48", "General", "No JavaScript errors during the test run", not errors, errors)
        b.close()

    with open(os.path.join(HERE, "results.json"), "w", encoding="utf-8") as f:
        json.dump(results, f, indent=1, ensure_ascii=False)
    passed = sum(r["pass"] for r in results)
    print(f"{passed}/{len(results)} passed")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())