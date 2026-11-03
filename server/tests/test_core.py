"""Unit tests for the pure calculation modules (SRS 7.4.4)."""
from datetime import date, datetime

import pytest

from app.core import bill, calc, weather
from app.core.forecast import forecast
from app.core.plan import usage_plan, what_if


def test_energy_and_cost():
    assert calc.energy_kwh(1000, 5) == 5.0                      # US-06
    assert calc.energy_kwh(150, 8) == pytest.approx(1.2)
    assert calc.cost(120, 12.5) == 1500.0                        # US-08


def test_projection_example_from_the_srs():
    assert calc.cost(calc.projected_cycle_kwh(119.349, 11, 31), 12.5) == pytest.approx(4204.34, abs=0.01)


def test_billing_cycle_starting_on_the_21st_and_short_months():
    c = calc.cycle_of(datetime(2026, 10, 31, 9, 40), 21)
    assert (c.start, c.end, c.days) == (datetime(2026, 10, 21), datetime(2026, 11, 21), 31)
    assert calc.day_index(c, datetime(2026, 10, 31, 9, 40)) == 11
    assert calc.cycle_of(datetime(2027, 2, 28), 31).start == datetime(2027, 2, 28)


def test_split_by_day_at_midnight():
    parts = list(calc.split_by_day(datetime(2026, 10, 31, 23), datetime(2026, 11, 1, 1, 30)))
    assert [round(h, 2) for _, h in parts] == [1.0, 1.5]
    assert parts[0][0].day == 31 and parts[1][0].day == 1


def test_above_usual():
    now = datetime(2026, 10, 31, 9)
    recs = [{"a": 1, "ts": datetime(2026, 10, 30 - i, 12) if i < 30 else datetime(2026, 9, 60 - i, 12),
             "kwh": 10 if i < 7 else 7} for i in range(35)]
    assert calc.above_usual(recs, 1, now)
    assert not calc.above_usual(recs, 2, now)


def _series(n, k, temps=None, start=datetime(2026, 10, 1)):
    from datetime import timedelta
    return [{"t": start + timedelta(days=i), "k": k(i), "T": temps[i] if temps else None} for i in range(n)]


def test_forecast_needs_seven_days():
    assert forecast(_series(4, lambda i: 10), datetime(2026, 10, 5), datetime(2026, 10, 5), datetime(2026, 10, 21), 0,
                    lambda d: None) == {"ok": False, "need": 3}


def test_flat_history_forecasts_the_same_level():
    f = forecast(_series(21, lambda i: 10), datetime(2026, 10, 22), datetime(2026, 10, 22), datetime(2026, 11, 21), 0,
                 lambda d: None)
    assert f["ok"] and len(f["next"]) == 7
    assert all(x["k"] == pytest.approx(10) for x in f["next"])
    assert f["model"] != "Weather-aware regression"  # no temperatures → weather model skipped


def test_weather_model_wins_when_heat_explains_use():
    temps = [31, 29.5, 33, 30, 34, 32, 29, 33.5, 30.5, 31.5, 34.5, 29, 32.5, 30, 33, 31, 34, 29.5, 32, 30.5, 33.5]
    s = _series(21, lambda i: 2 + 0.8 * temps[i], temps)
    nxt = {date(2026, 10, 22 + i): t for i, t in enumerate([34, 34, 33, 32, 31, 31, 30])}
    temp_for = lambda d: nxt.get(date(d.year, d.month, d.day)) or next((x["T"] for x in s if x["t"] == d), None)
    f = forecast(s, datetime(2026, 10, 21), datetime(2026, 10, 21), datetime(2026, 11, 21), 0, temp_for)
    assert f["model"] == "Weather-aware regression"
    assert 0.5 <= f["perDegree"] <= 1.0


def test_usage_plan_scales_non_essential_appliances_only():
    apps = [{"id": 1, "type": "AC", "watt": 1000, "essential": False}, {"id": 2, "type": "Fan", "watt": 60, "essential": False},
            {"id": 3, "type": "Fridge", "watt": 150, "essential": True}]
    p = usage_plan(apps, {1: 8, 2: 0.48, 3: 1.2}, {1: 2}, 300, 250, 10)   # 5 kWh a day
    assert p["needed"] and p["scale"] == pytest.approx(3.8 / 8.48)
    assert [i["a"]["id"] for i in p["items"]] == [1, 2]
    assert p["items"][0]["allowH"] == pytest.approx(8 * 3.8 / 8.48)
    assert usage_plan(apps, {1: 8, 2: 0.48, 3: 1.2}, {}, 300, 200, 10)["needed"] is False
    assert usage_plan(apps, {1: 8, 2: 0.48, 3: 1.2}, {}, 300, 320, 10)["scale"] == 0


def test_what_if_one_hour_less_air_con_and_inverter_payback():
    ac = [{"id": 1, "type": "Air conditioner", "watt": 1000, "essential": False}]
    r = what_if(ac, {1: 8}, {1: {"dh": -1}}, 12.5)
    assert (r["dK"], r["monthlyPeso"], r["payback"]) == (pytest.approx(-30), pytest.approx(-375), None)   # US-18
    r = what_if(ac, {1: 8}, {1: {"dh": 0, "inv": True}}, 12.5)
    assert r["dK"] == pytest.approx(-84) and r["payback"] == pytest.approx(12000 / 1050)


SAMPLE = ("ALBAY ELECTRIC COOPERATIVE\nBilling period: Sep 21 - Oct 20, 2026\nPresent reading: 15,559 Previous: 15,230\n"
          "KWH USED 329\nTotal amount due: 4,309.90")


def test_bill_text_parser():
    f = bill.parse_bill_text(SAMPLE)
    assert f == {"start": date(2026, 9, 21), "end": date(2026, 10, 20), "kwh": 329, "amount": 4309.90}
    assert bill.parse_bill_text("Period 09/21/2026 - 10/20/2026")["end"] == date(2026, 10, 20)
    assert bill.parse_bill_text("Dec 21 - Jan 20, 2027")["start"] == date(2026, 12, 21)
    assert set(bill.validate_bill(**{k: v for k, v in bill.parse_bill_text("nothing").items()})) == {"period", "kwh", "amount"}


def test_bill_comparison():
    c = bill.compare(329, 288.311, 4309.90)
    assert round(c["coverage"]) == 88 and c["eff"] == pytest.approx(13.1) and round(c["gapK"]) == 41


def test_weather_parsing_and_simulated_week():
    body = '{"daily":{"time":["2026-10-30","2026-10-31","2026-11-01"],"temperature_2m_max":[32.4,null,33.1]}}'
    assert weather.parse_open_meteo(body) == {"2026-10-30": 32.4, "2026-11-01": 33.1}
    assert weather.simulated_high(date(2026, 11, 1)) == 34
