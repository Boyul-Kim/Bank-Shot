"""SQLite persistence: source snapshots, settings, the live draft, and cached build results."""
import json
import os
import sqlite3
import threading
import time
from pathlib import Path

DB_PATH = Path(os.environ.get("AUCTION_DB", Path(__file__).resolve().parent.parent / "data" / "auction.db"))
_lock = threading.Lock()

SCHEMA = """
CREATE TABLE IF NOT EXISTS snapshots (
  id INTEGER PRIMARY KEY AUTOINCREMENT, source_id TEXT NOT NULL, retrieved_at REAL NOT NULL,
  url TEXT, method TEXT NOT NULL, status TEXT NOT NULL, error TEXT, row_count INTEGER, rows_json TEXT);
CREATE INDEX IF NOT EXISTS snap_src ON snapshots(source_id, status, id);
CREATE TABLE IF NOT EXISTS kv (key TEXT PRIMARY KEY, value_json TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS sales (
  id INTEGER PRIMARY KEY AUTOINCREMENT, player_id TEXT NOT NULL UNIQUE, team_id INTEGER NOT NULL,
  price INTEGER NOT NULL, at REAL NOT NULL);
CREATE TABLE IF NOT EXISTS build_cache (key TEXT PRIMARY KEY, results_json TEXT NOT NULL, created_at REAL NOT NULL);
"""


def connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB_PATH, timeout=30)
    con.row_factory = sqlite3.Row
    return con


def init():
    with _lock, connect() as con:
        con.executescript(SCHEMA)


# --- snapshots ---
def add_snapshot(source_id, method, url, rows=None, status="ok", error=None) -> int:
    with _lock, connect() as con:
        cur = con.execute(
            "INSERT INTO snapshots (source_id, retrieved_at, url, method, status, error, row_count, rows_json) VALUES (?,?,?,?,?,?,?,?)",
            (source_id, time.time(), url, method, status, error, len(rows) if rows else 0, json.dumps(rows) if rows else None))
        return cur.lastrowid


def _snap(row, with_rows=True):
    if row is None:
        return None
    d = dict(row)
    d["rows"] = json.loads(d.pop("rows_json")) if with_rows and d.get("rows_json") else None
    d.pop("rows_json", None)
    return d


def active_snapshot(source_id, with_rows=True):
    with connect() as con:
        return _snap(con.execute("SELECT * FROM snapshots WHERE source_id=? AND status='ok' ORDER BY id DESC LIMIT 1",
                                 (source_id,)).fetchone(), with_rows)


def last_attempt(source_id):
    with connect() as con:
        return _snap(con.execute("SELECT * FROM snapshots WHERE source_id=? ORDER BY id DESC LIMIT 1", (source_id,)).fetchone(), False)


# --- key/value ---
def get_kv(key, default=None):
    with connect() as con:
        row = con.execute("SELECT value_json FROM kv WHERE key=?", (key,)).fetchone()
    return json.loads(row["value_json"]) if row else default


def set_kv(key, value):
    with _lock, connect() as con:
        con.execute("INSERT INTO kv (key, value_json) VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value_json=excluded.value_json",
                    (key, json.dumps(value)))


# --- draft sales ---
def list_sales():
    with connect() as con:
        return [dict(r) for r in con.execute("SELECT * FROM sales ORDER BY id")]


def add_sale(player_id, team_id, price) -> int:
    with _lock, connect() as con:
        return con.execute("INSERT INTO sales (player_id, team_id, price, at) VALUES (?,?,?,?)",
                           (player_id, team_id, price, time.time())).lastrowid


def delete_sale(sale_id) -> bool:
    with _lock, connect() as con:
        return con.execute("DELETE FROM sales WHERE id=?", (sale_id,)).rowcount > 0


def clear_sales():
    with _lock, connect() as con:
        con.execute("DELETE FROM sales")


# --- build cache ---
def cache_get(key):
    with connect() as con:
        row = con.execute("SELECT results_json FROM build_cache WHERE key=?", (key,)).fetchone()
    return json.loads(row["results_json"]) if row else None


def cache_set(key, results):
    with _lock, connect() as con:
        con.execute("INSERT OR REPLACE INTO build_cache (key, results_json, created_at) VALUES (?,?,?)",
                    (key, json.dumps(results), time.time()))
