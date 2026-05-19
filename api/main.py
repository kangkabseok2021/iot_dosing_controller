"""FastAPI dashboard — reads dosing telemetry from SQLite."""

from __future__ import annotations

import os
import sqlite3
import time
from pathlib import Path

from collector.db import DEFAULT_DB, get_conn, init_db
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

app = FastAPI(title="IoT Dosing Controller Dashboard", version="0.1.0")

_START = time.monotonic()


def _db() -> str:
    return os.environ.get("DB_PATH", str(DEFAULT_DB))


# ── Health ─────────────────────────────────────────────────────────────────


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "uptime_s": round(time.monotonic() - _START, 1)}


# ── Live status (latest sensor snapshot) ──────────────────────────────────


@app.get("/api/status")
def status() -> dict:
    conn = get_conn(_db())
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT * FROM sensor_metrics ORDER BY ts DESC LIMIT 1").fetchone()
    conn.close()
    return dict(row) if row else {"message": "no data yet"}


# ── Dosing events ──────────────────────────────────────────────────────────


@app.get("/api/events")
def events(limit: int = 50) -> list[dict]:
    conn = get_conn(_db())
    rows = conn.execute("SELECT * FROM dosing_events ORDER BY ts DESC LIMIT ?", (limit,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ── Metrics time-series ────────────────────────────────────────────────────


@app.get("/api/metrics")
def metrics(last_n: int = 100) -> list[dict]:
    conn = get_conn(_db())
    rows = conn.execute(
        "SELECT * FROM sensor_metrics ORDER BY ts DESC LIMIT ?", (last_n,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ── Static dashboard (last — API routes take priority) ────────────────────


def create_app(db_path: str = "") -> FastAPI:
    if db_path:
        os.environ["DB_PATH"] = db_path
    init_db(db_path or _db())
    return app


_STATIC = Path(__file__).parent.parent / "static"
if _STATIC.exists():
    app.mount("/", StaticFiles(directory=str(_STATIC), html=True), name="static")
