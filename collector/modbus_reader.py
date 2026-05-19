"""Polls C++ daemon Modbus registers and writes to SQLite."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import UTC, datetime

from .db import get_conn, init_db, state_name

log = logging.getLogger(__name__)


@dataclass
class SensorSnapshot:
    ts: str
    flow_rate_ml_min: float
    valve_state: int
    dosing_state: str
    rfid_tag: str
    total_volume_ml: int


def parse_registers(regs: list[int]) -> SensorSnapshot:
    """Decode Modbus holding register array into a SensorSnapshot.

    Register layout (matches C++ ModbusServer):
      0: flow_rate × 10   1: valve_state
      2: total_vol high   3: total_vol low
      4-11: RFID EPC (8 × uint16)
      12: dosing_state
    """
    if len(regs) < 13:
        raise ValueError(f"Expected 13 registers, got {len(regs)}")

    flow = regs[0] / 10.0
    valve = regs[1]
    total_vol = (regs[2] << 16) | regs[3]
    epc_bytes = []
    for i in range(8):
        epc_bytes.append(chr((regs[4 + i] >> 8) & 0xFF))
        epc_bytes.append(chr(regs[4 + i] & 0xFF))
    rfid = "".join(epc_bytes).strip("\x00")
    state = state_name(regs[12])
    ts = datetime.now(UTC).isoformat()

    return SensorSnapshot(
        ts=ts,
        flow_rate_ml_min=flow,
        valve_state=valve,
        dosing_state=state,
        rfid_tag=rfid,
        total_volume_ml=total_vol,
    )


def write_metric(snap: SensorSnapshot, db_path: str) -> None:
    with get_conn(db_path) as conn:
        conn.execute(
            """INSERT OR REPLACE INTO sensor_metrics
               (ts, flow_rate_ml_min, valve_state, dosing_state, rfid_tag)
               VALUES (?,?,?,?,?)""",
            (snap.ts, snap.flow_rate_ml_min, snap.valve_state, snap.dosing_state, snap.rfid_tag),
        )


async def run_collector(host: str, port: int, db_path: str, poll_interval: float = 0.5) -> None:
    """Poll Modbus registers and write to SQLite.  Imported lazily to avoid
    pymodbus at import time (tests mock at the parse_registers level)."""
    from pymodbus.client import AsyncModbusTcpClient  # type: ignore[import]

    init_db(db_path)
    async with AsyncModbusTcpClient(host, port=port) as client:
        log.info("Modbus collector connected to %s:%d", host, port)
        while True:
            result = await client.read_holding_registers(0, 13)
            if not result.isError():
                try:
                    snap = parse_registers(list(result.registers))
                    write_metric(snap, db_path)
                except Exception as exc:
                    log.warning("Parse error: %s", exc)
            await asyncio.sleep(poll_interval)
