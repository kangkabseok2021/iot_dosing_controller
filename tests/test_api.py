"""FastAPI dashboard tests — no C++ daemon, no Modbus."""

import pytest
from collector.db import get_conn
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path, monkeypatch):
    db = str(tmp_path / "test.db")
    monkeypatch.setenv("DB_PATH", db)
    from api.main import app, create_app

    create_app(db)
    with TestClient(app) as c:
        yield c, db


def test_health(client):
    c, _ = client
    r = c.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_status_empty_db(client):
    c, _ = client
    r = c.get("/api/status")
    assert r.status_code == 200
    assert r.json() == {"message": "no data yet"}


def test_status_returns_latest_row(client):
    c, db = client
    with get_conn(db) as conn:
        conn.execute(
            "INSERT INTO sensor_metrics (ts, flow_rate_ml_min, valve_state, dosing_state, rfid_tag)"
            " VALUES (?,?,?,?,?)",
            ("2026-05-19T10:00:00", 150.0, 1, "DOSING", "AABB"),
        )
    r = c.get("/api/status")
    assert r.status_code == 200
    body = r.json()
    assert abs(body["flow_rate_ml_min"] - 150.0) < 0.01
    assert body["dosing_state"] == "DOSING"


def test_events_empty(client):
    c, _ = client
    r = c.get("/api/events")
    assert r.status_code == 200
    assert r.json() == []


def test_metrics_limit(client):
    c, db = client
    with get_conn(db) as conn:
        for i in range(5):
            conn.execute(
                "INSERT INTO sensor_metrics (ts, flow_rate_ml_min, valve_state, dosing_state)"
                " VALUES (?,?,?,?)",
                (f"2026-05-19T10:00:0{i}", float(i * 10), 0, "IDLE"),
            )
    r = c.get("/api/metrics", params={"last_n": 3})
    assert r.status_code == 200
    assert len(r.json()) == 3


def test_plc_decide_valve_opens_when_flow_ok():
    from plc_simulator.simulator import decide_valve

    # flow=600 (=60.0 ml/min × 10), state=DOSING(1) → valve open
    regs = [600] + [0] * 3 + [0] * 8 + [1]
    assert decide_valve(regs) is True


def test_plc_decide_valve_closes_when_complete():
    from plc_simulator.simulator import decide_valve

    # state=COMPLETE(3) → valve closed regardless of flow
    regs = [600] + [0] * 3 + [0] * 8 + [3]
    assert decide_valve(regs) is False
