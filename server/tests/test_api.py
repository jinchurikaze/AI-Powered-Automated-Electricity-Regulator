"""REST API tests mapped to the user stories (SRS 5.2.6). The Flutter app calls these endpoints."""
import pytest

from conftest import appliance_id


def test_us01_register_validation_and_login(client):
    r = client.post("/api/register", json={"email": "paolo@", "password": "short", "rate": "0", "consent": False})
    assert r.status_code == 400
    assert {"email", "password", "rate", "consent"} <= set(r.get_json()["errors"])
    r = client.post("/api/register", json={"email": "paolo@example.com", "password": "longenough1", "rate": "12.50",
                                          "cycleDay": 5, "monthlyLimit": "2000", "consent": True})
    assert r.status_code == 201
    tok = r.get_json()["token"]
    me = client.get("/api/me", headers={"Authorization": f"Bearer {tok}"}).get_json()
    assert me["rate"] == 12.5 and me["cycleDay"] == 5 and me["simulated"] is False
    assert client.post("/api/register", json={"email": "paolo@example.com", "password": "longenough1", "rate": "12",
                                              "consent": True}).get_json()["errors"]["email"] == "Email already in use."
    assert client.post("/api/login", json={"email": "paolo@example.com", "password": "wrong"}).status_code == 401
    assert client.post("/api/login", json={"email": "paolo@example.com", "password": "longenough1"}).status_code == 200


def test_requests_without_a_token_are_refused(client):
    assert client.get("/api/dashboard").status_code == 401                         # NFR-SEC-1


def test_us02_rate_validation(demo):
    assert demo.put("/api/settings", json={"rate": "0", "cycleDay": 21}).status_code == 400
    assert demo.put("/api/settings", json={"rate": "12.50", "cycleDay": 21}).get_json()["rate"] == 12.5


def test_us03_wattage_validation_and_add(demo):
    for w in ("0", "20000", "abc"):
        r = demo.post("/api/appliances", json={"type": "Other", "watt": w})
        assert r.status_code == 400 and r.get_json()["errors"]["watt"] == "Enter a wattage from 1 to 10,000 W."
    r = demo.post("/api/appliances", json={"type": "Other", "watt": "1,000", "hours": "2", "essential": True})
    assert r.status_code == 201 and r.get_json()["appliance"]["essential"] is True


def test_us04_deleted_appliance_keeps_its_usage(demo):
    before = demo.get("/api/dashboard").get_json()["cycleKwh"]
    tv = appliance_id(demo, "Television")
    assert demo.delete(f"/api/appliances/{tv}").status_code == 200
    assert all(a["type"] != "Television" for a in demo.get("/api/appliances").get_json()["appliances"])
    assert demo.get("/api/dashboard").get_json()["cycleKwh"] == pytest.approx(before)


def test_us05_timer_start_stop(demo):
    tv = appliance_id(demo, "Television")
    assert demo.post(f"/api/appliances/{tv}/start").get_json()["appliance"]["running"] is True
    demo.post("/api/demo/advance", json={"hours": 2})
    r = demo.post(f"/api/appliances/{tv}/stop").get_json()
    assert r["recordedHours"] == pytest.approx(2)
    assert r["recent"][0]["src"] == "TIMER" and r["recent"][0]["kwh"] == pytest.approx(0.24)


def test_us05_home_lists_running_timers(demo):
    d = demo.get("/api/dashboard").get_json()
    assert [a["type"] for a in d["running"]] == ["Electric fan"]
    assert d["running"][0]["elapsedH"] == pytest.approx(70 / 60, abs=1e-3)


def test_us06_logged_hours_and_limits(demo):
    tv = appliance_id(demo, "Television")
    before = demo.get("/api/dashboard").get_json()["todayKwh"]
    r = demo.post(f"/api/appliances/{tv}/log", json={"hours": "2"})
    assert r.status_code == 200 and r.get_json()["recent"][0]["src"] == "LOGGED"
    assert demo.get("/api/dashboard").get_json()["todayKwh"] - before == pytest.approx(0.24)
    assert demo.post(f"/api/appliances/{tv}/log", json={"hours": "30"}).status_code == 400
    assert demo.post(f"/api/appliances/{tv}/log", json={"hours": "23"}).status_code == 400   # 2 + 23 > 24 h


def test_log_many_skips_empty_entries(demo):
    tv, wm = appliance_id(demo, "Television"), appliance_id(demo, "Washing machine")
    r = demo.post("/api/log", json={"hours": {str(tv): "1", str(wm): ""}})
    assert r.status_code == 200 and r.get_json()["errors"] == {}


def test_us07_us08_summaries_and_costs(demo):
    u = demo.get("/api/usage").get_json()
    assert u["cycleKwh"] == pytest.approx(119.349, abs=0.01)
    assert u["cycleCost"] == pytest.approx(119.349 * 12.5, abs=0.02)
    assert u["projCost"] == pytest.approx(4204.34, abs=0.01)
    assert len(u["bars"]) == 7 and u["bars"][-1]["label"] == "Today"
    assert demo.get("/api/usage?view=monthly").get_json()["bars"][-1]["label"] == "This cycle"


def test_us09_ranking_and_above_usual(demo):
    shares = demo.get("/api/usage").get_json()["shares"]
    assert shares[0]["type"] == "Air conditioner" and round(shares[0]["share"]) == 81
    assert shares[0]["aboveUsual"] is True
    assert sum(s["share"] for s in shares) == pytest.approx(100)


def test_us10_alerts_once_per_cycle(demo):
    r = demo.post("/api/demo/use", json={"pct": 80}).get_json()
    titles = [n["title"] for n in r["newNotifications"]]
    assert "80% of your monthly limit used" in titles and "Usage plan ready" in titles
    r = demo.post("/api/demo/advance", json={"hours": 2}).get_json()
    assert "80% of your monthly limit used" not in [n["title"] for n in r["newNotifications"]]
    r = demo.post("/api/demo/use", json={"pct": 100}).get_json()
    assert "Monthly limit reached" in [n["title"] for n in r["newNotifications"]]
    alerts = demo.get("/api/limits").get_json()["alerts"]
    assert sorted(a["threshold"] for a in alerts if a["period_key"] == "2026-10-21") == [80, 100]


def test_us11_us15_weather_aware_forecast(demo):
    s = demo.get("/api/save").get_json()
    f = s["forecast"]
    assert f["model"] == "Weather-aware regression" and f["mae"] == pytest.approx(0.385, abs=0.001)
    assert f["perDegree"] == pytest.approx(0.806, abs=0.001)
    assert [x["tmax"] for x in f["next"]] == [34, 34, 33, 32, 31, 31, 30]
    assert f["projCost"] == pytest.approx(4068.37, abs=0.01)


def test_us11_new_user_needs_seven_days(client):
    tok = client.post("/api/register", json={"email": "new@example.com", "password": "longenough1", "rate": "12.5",
                                             "monthlyLimit": "3000", "consent": True}).get_json()["token"]
    s = client.get("/api/save", headers={"Authorization": f"Bearer {tok}"}).get_json()
    assert s["forecast"] is None and s["need"] == 7


def test_us12_tips_savings_and_dismiss(demo):
    tips = demo.get("/api/save").get_json()["tips"]
    ac = next(t for t in tips if t["title"] == "Air conditioner: use it 1 hour less per day")
    assert ac["kwh"] == 30 and ac["peso"] == 375
    assert tips[0]["stay"] is True                       # keeps the user within the limit → first
    demo.post(f"/api/tips/{ac['key']}", json={"status": "DISMISSED"})
    assert ac["key"] not in [t["key"] for t in demo.get("/api/save").get_json()["tips"]]


def test_us13_plan_allowances(demo):
    p = demo.get("/api/save").get_json()["plan"]
    assert p["needed"] and p["daysLeft"] == 21
    assert p["daily"] == pytest.approx(9.868, abs=0.001) and p["scale"] == pytest.approx(0.887, abs=0.001)
    assert "Refrigerator" not in [i["type"] for i in p["items"]]
    assert all(i["allowH"] <= i["usualH"] for i in p["items"])
    assert demo.post("/api/plan", json={"active": True}).get_json()["plan"]["active"] is True


def test_us14_reminders_once_per_day(demo):
    demo.post("/api/plan", json={"active": True})
    titles = []
    for _ in range(14):
        titles += [n["title"] for n in demo.post("/api/demo/advance", json={"hours": 1}).get_json()["newNotifications"]]
    assert titles.count("15 minutes left for Electric fan") == 1
    assert titles.count("Time to turn off the electric fan") == 1


def test_us16_bill_check_parse_save_and_rate(demo):
    c = demo.get("/api/check").get_json()["bill"]
    assert round(c["coverage"]) == 88 and round(c["missingKwh"]) == 41 and c["rate"] == pytest.approx(13.1)
    f = demo.post("/api/bills/parse", json={"text": "Billing period: Sep 21 - Oct 20, 2026\nKWH USED 329\nTotal amount due 4,309.90"}).get_json()
    assert f == {"start": "2026-09-21", "end": "2026-10-20", "kwh": 329.0, "amount": 4309.9}
    bad = demo.post("/api/bills", json={"start": "2026-10-20", "end": "2026-09-21", "kwh": 0, "amount": 100})
    assert bad.status_code == 400 and {"period", "kwh"} <= set(bad.get_json()["errors"])
    assert demo.post("/api/bills", json={**f, "src": "SCAN"}).status_code == 201
    assert demo.post("/api/bills/use-rate").get_json()["rate"] == 13.1


def test_us17_meter_readings(demo):
    m = demo.get("/api/check").get_json()
    last = m["readings"][0]["reading"]
    assert demo.post("/api/meter", json={"reading": last - 5}).status_code == 400
    r = demo.post("/api/meter", json={"reading": last + 120}).get_json()
    assert r["meter"]["measured"] == pytest.approx(120)


def test_us18_what_if(demo):
    ac = appliance_id(demo, "Air conditioner")
    r = demo.post("/api/whatif", json={"changes": {str(ac): {"dh": -1}}}).get_json()["result"]
    assert r["monthlyKwh"] == pytest.approx(-30) and r["monthlyPeso"] == pytest.approx(-375)
    r = demo.post("/api/whatif", json={"changes": {str(ac): {"dh": 0, "inv": True}}}).get_json()["result"]
    assert r["payback"] is not None and r["monthlyPeso"] < 0


def test_export_and_delete_account(demo):
    assert demo.get("/api/export").get_json()["records"] > 100
    assert demo.delete("/api/account").status_code == 200
    assert demo.get("/api/me").status_code == 401
