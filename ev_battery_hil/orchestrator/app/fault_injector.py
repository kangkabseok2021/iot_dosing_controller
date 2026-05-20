import asyncio
import logging
import os
import socket

from .client import OrchestratorClient

log = logging.getLogger(__name__)


def _send_watchdog_ping() -> None:
    notify_socket = os.environ.get("NOTIFY_SOCKET")
    if not notify_socket:
        return
    try:
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
        sock.sendto(b"WATCHDOG=1", notify_socket)
        sock.close()
    except OSError as exc:
        log.debug("Watchdog ping failed: %s", exc)


async def _watchdog_loop() -> None:
    while True:
        await asyncio.sleep(10)
        _send_watchdog_ping()


class FaultInjector:
    def __init__(self, client: OrchestratorClient) -> None:
        self._client = client
        self._watchdog_task: asyncio.Task | None = None

    def start(self) -> None:
        self._watchdog_task = asyncio.create_task(_watchdog_loop())

    async def stop(self) -> None:
        if self._watchdog_task:
            self._watchdog_task.cancel()
            try:
                await self._watchdog_task
            except asyncio.CancelledError:
                pass

    async def inject(self, fault_type: str, params: dict | None = None) -> None:
        match fault_type:
            case "THERMAL_RUNAWAY":
                await self._thermal_runaway()
            case "SENSOR_DROPOUT":
                await self._sensor_dropout(params or {})
            case "OVERCURRENT":
                await self._overcurrent()
            case _:
                raise ValueError(f"Unknown fault type: {fault_type}")

    async def _thermal_runaway(self) -> None:
        log.info("Injecting THERMAL_RUNAWAY: blocking cooling vent")
        await self._client.send_command("SET_FAULT", "THERMAL_RUNAWAY")

    async def _sensor_dropout(self, params: dict) -> None:
        duration = float(params.get("duration_s", 5))
        log.info("Injecting SENSOR_DROPOUT for %.0fs", duration)
        await self._client.disconnect()
        await asyncio.sleep(duration)
        log.info("SENSOR_DROPOUT complete — client reconnect in progress")

    async def _overcurrent(self) -> None:
        log.info("Injecting OVERCURRENT: sending 300 A (limit 250 A)")
        await self._client.send_command("SET_CURRENT", 300.0)
