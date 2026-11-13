"""Persistent pipeline state (SQLite, stdlib). Safe for one worker + the dashboard concurrently (WAL)."""
from __future__ import annotations

import datetime as dt
import json
import sqlite3
from pathlib import Path

from .. import VAR

DB_PATH = VAR / "n4v3d_media.db"

STAGES = ["IDEA", "RESEARCH", "FACT_CHECK", "SCRIPT", "STORYBOARD", "ASSETS", "ANIMATION", "VOICE", "EDIT",
          "QUALITY_REVIEW", "APPROVAL", "PUBLISH", "ANALYTICS", "IMPROVEMENT", "DONE"]
STATUSES = ["pending", "running", "waiting", "blocked", "failed", "done"]

SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  path TEXT NOT NULL, prod_id TEXT, title TEXT,
  stage TEXT NOT NULL DEFAULT 'IDEA', status TEXT NOT NULL DEFAULT 'pending',
  attempts INTEGER NOT NULL DEFAULT 0, last_error TEXT, wait_reason TEXT,
  next_run_at TEXT, heartbeat TEXT,
  approved_by TEXT, approved_at TEXT,
  created TEXT, updated TEXT, artifacts TEXT DEFAULT '{}'
);
CREATE TABLE IF NOT EXISTS events (
  id INTEGER PRIMARY KEY AUTOINCREMENT, job_id INTEGER, ts TEXT, stage TEXT, level TEXT, message TEXT
);
CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE IF NOT EXISTS ledger (
  id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT, kind TEXT CHECK(kind IN ('revenue','expense')),
  amount REAL, currency TEXT, description TEXT, created TEXT
);
"""


def now():
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def connect(path: Path | None = None) -> sqlite3.Connection:
    path = Path(path or DB_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path, timeout=30, isolation_level=None)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")
    con.executescript(SCHEMA)
    return con


def log(con, job_id, stage, level, message):
    con.execute("INSERT INTO events(job_id, ts, stage, level, message) VALUES (?,?,?,?,?)", (job_id, now(), stage, level, message))
    if level in ("error", "action", "blocked"):
        from . import notify
        notify.send(level, message, job_id=job_id, stage=stage)


def get_setting(con, key, default=None):
    r = con.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    return json.loads(r["value"]) if r else default


def set_setting(con, key, value):
    con.execute("INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, json.dumps(value)))


def emergency_stopped(con) -> bool:
    return bool(get_setting(con, "emergency_stop", False)) or (VAR / "STOP").exists()


def enqueue(con, path, prod_id=None, title=None):
    t = now()
    cur = con.execute("INSERT INTO jobs(path, prod_id, title, created, updated) VALUES (?,?,?,?,?)", (str(path), prod_id, title, t, t))
    log(con, cur.lastrowid, "IDEA", "info", f"enqueued {path}")
    return cur.lastrowid


def update(con, job_id, **fields):
    fields["updated"] = now()
    cols = ", ".join(f"{k}=?" for k in fields)
    con.execute(f"UPDATE jobs SET {cols} WHERE id=?", (*fields.values(), job_id))


def jobs(con):
    return [dict(r) for r in con.execute("SELECT * FROM jobs ORDER BY id DESC")]


def events(con, limit=100, job_id=None):
    if job_id:
        q = con.execute("SELECT * FROM events WHERE job_id=? ORDER BY id DESC LIMIT ?", (job_id, limit))
    else:
        q = con.execute("SELECT * FROM events ORDER BY id DESC LIMIT ?", (limit,))
    return [dict(r) for r in q]
