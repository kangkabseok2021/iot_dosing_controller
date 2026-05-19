"""Collector tests — parse_registers + SQLite write (no Modbus broker needed)."""

import pytest
from collector.db import get_conn, init_db, state_name
from collector.modbus_reader import SensorSnapshot, parse_registers, write_metric


def _make_regs(
    flow_x10: int = 2000, valve: int = 1, vol_hi: int = 0, vol_lo: int = 500, state: int = 1
) -> list[int]:
    """Build a valid 13-register array."""
    epc = [0x4142, 0x4344, 0x4546, 0x4748, 0x4142, 0x4344, 0x4546, 0x4748]  # "ABCDEFGHAB..."
    return [flow_x10, valve, vol_hi, vol_lo] + epc + [state]


def test_parse_flow_rate():
    regs = _make_regs(flow_x10=1234)
    snap = parse_registers(regs)
    assert abs(snap.flow_rate_ml_min - 123.4) < 0.01


def test_parse_valve_state():
    snap = parse_registers(_make_regs(valve=1))
    assert snap.valve_state == 1


def test_parse_dosing_state_dosing():
    snap = parse_registers(_make_regs(state=1))
    assert snap.dosing_state == "DOSING"


def test_parse_total_volume():
    snap = parse_registers(_make_regs(vol_hi=0, vol_lo=999))
    assert snap.total_volume_ml == 999


def test_parse_too_few_registers_raises():
    with pytest.raises(ValueError):
        parse_registers([0] * 5)


def test_state_name_mapping():
    assert state_name(0) == "IDLE"
    assert state_name(1) == "DOSING"
    assert state_name(2) == "PAUSE"
    assert state_name(3) == "COMPLETE"
    assert state_name(99) == "UNKNOWN"


def test_write_metric_persists(tmp_path):
    db = str(tmp_path / "test.db")
    init_db(db)
    snap = SensorSnapshot(
        ts="2026-05-19T10:00:00+00:00",
        flow_rate_ml_min=200.0,
        valve_state=1,
        dosing_state="DOSING",
        rfid_tag="AABB",
        total_volume_ml=500,
    )
    write_metric(snap, db)
    row = get_conn(db).execute("SELECT * FROM sensor_metrics WHERE ts=?", (snap.ts,)).fetchone()
    assert row is not None
    assert abs(row["flow_rate_ml_min"] - 200.0) < 0.01
    assert row["dosing_state"] == "DOSING"
