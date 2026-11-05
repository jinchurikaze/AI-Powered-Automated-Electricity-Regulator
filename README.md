# AI-Powered Electricity Regulator — PD8 prototype

Group 9 · BSCS 3A · Bicol University College of Science · Software Engineering, 1st Semester SY 2026–2027

The app helps households in Legazpi City keep their electric bill within a limit **using only what they enter**, with no
smart plug or other hardware. The user starts and stops a timer when they turn an appliance on and off, or logs the
hours later. The system then:

- estimates kWh and pesos;
- warns at 80% and 100% of the limit;
- forecasts the rest of the billing cycle using the weather;
- gives a daily usage plan with reminders;
- compares the electric bill with what was recorded (Bill Check);
- shows what a change would save (what-if).

| Part | Folder | Technology |
| --- | --- | --- |
| Server: database, rules, forecast, plan, Bill Check, REST API, demo web pages | `server/` | Python 3.10+, Flask, SQLite |
| Phone app (client of the server's API) | `lib/`, `test/` | Flutter 3.27+ (Dart), Provider, http, ML Kit |

## 1. Run the server (Python)

```bash
cd server
python -m venv .venv
.venv\Scripts\activate          # Windows   (macOS/Linux: source .venv/bin/activate)
pip install -r requirements.txt
python run.py
```

Open **http://localhost:5000** and choose **Open sample household**. The sample has 40 days of usage, a ₱4,000 limit,
and a demo clock set to Oct 31, 2026, 9:40 AM. Its demo controls (beside the phone) move time, reach 80% or 100% of
the limit, or reload the sample. **Create account** starts a real account on today's date, with temperatures from
Open-Meteo (internet needed).

- The database is created at `server/instance/electricity_regulator.sqlite`.
- Settings use environment variables: `PORT`, `DATABASE`, `SECRET_KEY`, `FETCH_WEATHER=0` (offline).

### Test the server

```bash
cd server
python -m pytest -q                                   # 38 unit and API tests
pip install playwright && playwright install chromium
python run.py                                         # in another terminal
python acceptance/run_acceptance.py                   # 48 browser acceptance tests → acceptance/results.json
```

## Host the server online (Render, free)

The repository includes `render.yaml`, so Render can set everything up from GitHub:

1. Sign in at https://render.com with GitHub.
2. Choose **New → Blueprint**, pick this repository, and click **Apply**.
3. Wait for the first deploy, then open the `https://…onrender.com` link and choose **Open sample household**.

Free-plan notes: the server sleeps after 15 minutes without visitors and takes about a minute to wake up, and its
SQLite database is reset when it sleeps, restarts, or redeploys (the sample household is rebuilt each time). Every push
to `main` redeploys automatically. In the phone app, enter the `https://` link as the server address.

## 2. Run the phone app (Flutter)

```bash
flutter create --project-name electricity_regulator --org ph.edu.bu.group9 --platforms android .   # adds android/
flutter pub get
flutter test
flutter run
```

After `flutter create`, edit `android/app/src/main/AndroidManifest.xml`:

- above `<application`, add `<uses-permission android:name="android.permission.INTERNET"/>`;
- in the `<application ...>` tag, add `android:usesCleartextTraffic="true"`, so the app can reach the Flask server over
  plain HTTP on your network.

On the first screen, enter the server address, then choose **Open sample household** or sign in:

- **Android emulator:** `http://10.0.2.2:5000`
- **Phone on the same Wi-Fi as the laptop:** `http://<laptop IP>:5000`. Find the IP with `ipconfig` on Windows. Allow
  Python through the firewall.

The phone reads bill photos with ML Kit (minSdk 21) and sends only the text to the server.

## Run and test in VS Code

Open the project folder (the one with `README.md`) in VS Code and install the recommended extensions when asked
(Python, Flutter).

1. **Terminal → Run Task… → Set up server (venv + packages)** (once). Then pick the interpreter
   `server\.venv` when VS Code asks (or Ctrl+Shift+P → *Python: Select Interpreter*).
2. **Run and Debug** (Ctrl+Shift+D):
   - **Server (Flask)** → F5, then open http://localhost:5000;
   - **Server tests (pytest)** (or the Testing panel, the flask icon on the left);
   - **Acceptance tests (server must be running)**;
   - **Flutter app** or **Server + Flutter app** (after **Run Task… → Set up Flutter app** and the
     AndroidManifest changes in Section 2).

## API (used by the Flutter app)

All endpoints are under `/api`, use JSON, and need `Authorization: Bearer <token>` except `register`, `login`, and
`demo`. The full list is in SRS Section 7.4.3. Examples:

- `POST /api/demo`
- `GET /api/dashboard`
- `POST /api/appliances/{id}/start`
- `POST /api/appliances/{id}/stop`
- `POST /api/appliances/{id}/log`
- `GET /api/save`
- `POST /api/plan`
- `POST /api/bills/parse`
- `POST /api/bills`
- `POST /api/whatif`
- `POST /api/demo/advance`

## Code layout

```
server/
  run.py                    start the server
  app/__init__.py           Flask app factory
  app/db.py                 SQLite schema (SRS 7.4.1)
  app/core/                 calc, forecast (3 models), plan + what-if, bill parser, weather, recommendations
  app/household.py          one user's rules: timers, logging, limits, alerts, plan reminders, bills, meter
  app/views.py              screen data shared by the API and the web pages
  app/api.py                REST API for the Flutter app
  app/web.py, templates/    web pages for demonstrations
  tests/                    pytest unit and API tests
  acceptance/               Playwright browser acceptance tests
lib/
  api/api_client.dart       REST client
  state/app_state.dart      Provider state; calls the API
  services/bill_service.dart ML Kit text recognition on the phone
  ui/screens/               Home, Appliances, Usage, Save, What-if, Check, Bill, Log hours, Settings, Connect
test/                       Flutter unit tests (API client with a mock server, formats)
```

## Team workflow

1. Create a branch per backlog item, for example `feature/us-16-bill-check`.
2. Open a pull request and get one review before merging (SRS 5.1.1).
3. GitHub Actions runs the server tests and the Flutter analysis and tests on every pull request.
