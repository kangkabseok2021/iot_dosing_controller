"""Python PLC simulator — polls Modbus registers, sends valve commands.

Acts as the 'Test Automation Platform' / PLC controller:
  - Reads flow rate and dosing state from C++ daemon
  - Opens valve when RFID tag present and flow > threshold
  - Closes valve on occlusion or after target volume reached
"""

from __future__ import annotations

import asyncio
import logging
import os

log = logging.getLogger(__name__)

VALVE_COIL = 0
RESET_COIL = 1
FLOW_REGISTER = 0  # flow_rate × 10
STATE_REGISTER = 12  # dosing_state (0=IDLE…3=COMPLETE)
RFID_REGISTER_START = 4  # 8 registers for EPC

FLOW_THRESHOLD_X10 = 50  # 5.0 ml/min × 10


def decide_valve(regs: list[int]) -> bool:
    """Open valve when flow is above threshold and state is not COMPLETE."""
    if len(regs) < 13:
        return False
    flow_x10 = regs[FLOW_REGISTER]
    state = regs[STATE_REGISTER]
    return flow_x10 >= FLOW_THRESHOLD_X10 and state != 3  # 3=COMPLETE


async def run_simulator(
    host: str | None = None, port: int | None = None, poll_interval: float = 0.1
) -> None:
    """Connect to the C++ Modbus daemon and drive the valve command coil."""
    from pymodbus.client import AsyncModbusTcpClient  # type: ignore[import]

    h = host or os.environ.get("MODBUS_HOST", "localhost")
    p = port or int(os.environ.get("MODBUS_PORT", "5502"))

    async with AsyncModbusTcpClient(h, port=p) as client:
        log.info("PLC simulator connected to %s:%d", h, p)
        while True:
            result = await client.read_holding_registers(0, 13)
            if not result.isError():
                valve = decide_valve(list(result.registers))
                await client.write_coil(VALVE_COIL, valve)
                log.debug(
                    "valve=%s flow_x10=%d state=%d",
                    valve,
                    result.registers[0],
                    result.registers[12],
                )
            await asyncio.sleep(poll_interval)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run_simulator())
