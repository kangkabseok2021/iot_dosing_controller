"""SQLite schema and helpers for dosing telemetry."""

from __future__ import annotations

import sqlite3
from pathlib import Path

DEFAULT_DB = Path("data/dosing.db")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS dosing_events (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    ts             TEXT    NOT NULL DEFAULT (datetime('now')),
    rfid_tag       TEXT    NOT NULL,
    volume_ml      REAL    NOT NULL,
    duration_s     REAL    NOT NULL,
    dosing_state   TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS sensor_metrics (
    ts               TEXT    NOT NULL,
    flow_rate_ml_min REAL    NOT NULL,
    valve_state      INTEGER NOT NULL,
    dosing_state     TEXT    NOT NULL,
    rfid_tag         TEXT    DEFAULT '',
    PRIMARY KEY (ts)
);

CREATE INDEX IF NOT EXISTS idx_metrics_ts ON sensor_metrics(ts);
"""

_DOSING_STATES = {0: "IDLE", 1: "DOSING", 2: "PAUSE", 3: "COMPLETE"}


def get_conn(db_path: str | Path = DEFAULT_DB) -> sqlite3.Connection:
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db(db_path: str | Path = DEFAULT_DB) -> None:
    with get_conn(db_path) as conn:
        conn.executescript(_SCHEMA)


def state_name(code: int) -> str:
    return _DOSING_STATES.get(code, "UNKNOWN")
