"""Web pages render and the main forms work."""


def test_landing_and_demo_pages(client):
    assert b"Open sample household" in client.get("/").data
    assert client.post("/demo").status_code == 302
    for path in ["/home", "/appliances", "/usage", "/usage?view=monthly", "/save", "/check", "/whatif", "/log",
                 "/settings", "/limits", "/notifications", "/help", "/data", "/bills/new", "/appliances/new"]:
        assert client.get(path).status_code == 200, path


def test_web_register_validation(client):
    r = client.post("/register", data={"email": "x", "password": "1", "rate": "0", "cycle_day": "1"})
    assert b"Enter a valid email address." in r.data and b"Please agree to the Privacy Notice" in r.data


def test_web_bill_sample_scan_fills_the_form(client):
    client.post("/demo")
    r = client.post("/bills/new", data={"act": "sample"})
    assert b'value="2026-09-21"' in r.data and b'value="329"' in r.data and b'value="4309.90"' in r.data


def test_web_timer_and_toast(client):
    client.post("/demo")
    client.post("/plan", data={"active": "1"})
    for _ in range(4):
        client.post("/demo/hour")
    r = client.get("/home")
    assert r.status_code == 200
