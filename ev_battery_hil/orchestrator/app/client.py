import asyncio
import json
import logging
from typing import Optional

from .models import TelemetryFrame

log = logging.getLogger(__name__)

_RECONNECT_DELAYS = [1, 2, 4, 8, 16, 30]


class OrchestratorClient:
    def __init__(self, host: str = "localhost", port: int = 5555) -> None:
        self._host = host
        self._port = port
        self._writer: Optional[asyncio.StreamWriter] = None
        self._last_frame: Optional[TelemetryFrame] = None
        self._running = False
        self._connect_task: Optional[asyncio.Task] = None

    async def start(self) -> None:
        self._running = True
        self._connect_task = asyncio.create_task(self._connect_loop())

    async def stop(self) -> None:
        self._running = False
        if self._writer:
            try:
                self._writer.close()
                await self._writer.wait_closed()
            except Exception:
                pass
        if self._connect_task:
            self._connect_task.cancel()
            try:
                await self._connect_task
            except asyncio.CancelledError:
                pass

    async def disconnect(self) -> None:
        """Close the current connection; _connect_loop will reconnect automatically."""
        if self._writer:
            try:
                self._writer.close()
                await self._writer.wait_closed()
            except Exception:
                pass

    async def send_command(self, command: str, value: str | float | None = None) -> None:
        if not self._writer:
            log.warning("send_command: not connected")
            return
        msg: dict = {"command": command}
        if value is not None:
            msg["value"] = value
        try:
            self._writer.write((json.dumps(msg) + "\n").encode())
            await self._writer.drain()
        except Exception as e:
            log.error("send_command failed: %s", e)

    @property
    def last_frame(self) -> Optional[TelemetryFrame]:
        return self._last_frame

    async def _connect_loop(self) -> None:
        delay_idx = 0
        while self._running:
            try:
                reader, writer = await asyncio.open_connection(self._host, self._port)
                self._writer = writer
                delay_idx = 0
                log.info("Connected to BMS daemon at %s:%d", self._host, self._port)
                await self._read_loop(reader)
            except (ConnectionRefusedError, OSError) as exc:
                delay = _RECONNECT_DELAYS[min(delay_idx, len(_RECONNECT_DELAYS) - 1)]
                log.warning("Connection failed (%s), retry in %ds", exc, delay)
                delay_idx += 1
                if self._running:
                    await asyncio.sleep(delay)
            finally:
                self._writer = None

    async def _read_loop(self, reader: asyncio.StreamReader) -> None:
        while self._running:
            try:
                line = await reader.readline()
                if not line:
                    break
                self._last_frame = TelemetryFrame.model_validate_json(line)
            except Exception as exc:
                log.error("Read error: %s", exc)
                break
