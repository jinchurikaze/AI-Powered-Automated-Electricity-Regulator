"""SQLite database (SRS 7.4.1). One file; every table is keyed by user_id (AD-03)."""
from __future__ import annotations

import sqlite3
from datetime import datetime

from flask import current_app, g

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  email TEXT UNIQUE NOT NULL,
  password_hash TEXT NOT NULL,
  rate REAL NOT NULL DEFAULT 0,
  cycle_day INTEGER NOT NULL DEFAULT 1,
  alerts_enabled INTEGER NOT NULL DEFAULT 1,
  simulated INTEGER NOT NULL DEFAULT 0,      -- 1 = demo clock (sample household)
  clock TEXT,                                -- demo clock time when simulated
  plan_active INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS tokens (
  token TEXT PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS appliances (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  type TEXT NOT NULL, brand TEXT NOT NULL DEFAULT '', model TEXT NOT NULL DEFAULT '',
  watt INTEGER NOT NULL, location TEXT NOT NULL DEFAULT '', hours REAL NOT NULL DEFAULT 0,
  essential INTEGER NOT NULL DEFAULT 0,
  timer_start TEXT,                          -- set while the usage timer runs
  deleted INTEGER NOT NULL DEFAULT 0         -- removed from the list; usage is kept (REQ-APL-4)
);
CREATE TABLE IF NOT EXISTS usage (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  appliance_id INTEGER NOT NULL, ts TEXT NOT NULL, hours REAL NOT NULL, kwh REAL NOT NULL,
  src TEXT NOT NULL CHECK (src IN ('TIMER','LOGGED'))
);
CREATE INDEX IF NOT EXISTS usage_user_ts ON usage(user_id, ts);
CREATE TABLE IF NOT EXISTS limits (
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  period TEXT NOT NULL CHECK (period IN ('monthly','daily')), unit TEXT NOT NULL CHECK (unit IN ('KWH','PESO')),
  value REAL NOT NULL DEFAULT 0, active INTEGER NOT NULL DEFAULT 0, PRIMARY KEY (user_id, period)
);
CREATE TABLE IF NOT EXISTS alerts (
  id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  period TEXT NOT NULL, threshold INTEGER NOT NULL, period_key TEXT NOT NULL, sent_at TEXT NOT NULL,
  amount REAL NOT NULL, unit TEXT NOT NULL, UNIQUE (user_id, period, threshold, period_key)
);
CREATE TABLE IF NOT EXISTS notifications (
  id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  title TEXT NOT NULL, body TEXT NOT NULL, ts TEXT NOT NULL, read INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS tip_feedback (
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE, key TEXT NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('HELPFUL','DISMISSED')), ts TEXT NOT NULL, PRIMARY KEY (user_id, key)
);
CREATE TABLE IF NOT EXISTS plan_offered (
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE, cycle_key TEXT NOT NULL, PRIMARY KEY (user_id, cycle_key)
);
CREATE TABLE IF NOT EXISTS plan_notes (
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE, day_key TEXT NOT NULL, appliance_id INTEGER NOT NULL,
  warn INTEGER NOT NULL DEFAULT 0, over INTEGER NOT NULL DEFAULT 0, PRIMARY KEY (user_id, day_key, appliance_id)
);
CREATE TABLE IF NOT EXISTS bills (
  id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  start TEXT NOT NULL, end TEXT NOT NULL, kwh REAL NOT NULL, amount REAL NOT NULL,
  src TEXT NOT NULL CHECK (src IN ('SCAN','MANUAL')), ts TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS meter (
  id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  ts TEXT NOT NULL, reading REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS weather (
  day TEXT PRIMARY KEY, tmax REAL NOT NULL, fetched_at TEXT NOT NULL
);
"""

TS = "%Y-%m-%d %H:%M:%S"


def ts(t: datetime) -> str:
    return t.strftime(TS)


def parse_ts(s: str) -> datetime:
    return datetime.strptime(s, TS)


def connect(path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(path, detect_types=0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def get_db() -> sqlite3.Connection:
    if "db" not in g:
        g.db = connect(current_app.config["DATABASE"])
    return g.db


def close_db(_exc=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db(conn: sqlite3.Connection):
    conn.executescript(SCHEMA)
    conn.commit()
