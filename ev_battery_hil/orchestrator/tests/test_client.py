import asyncio
import json
import pytest
from orchestrator.app.client import OrchestratorClient
from orchestrator.app.models import TelemetryFrame

_FRAME = {
    "ts_us": 1000, "SoC": 0.8, "V_terminal": 3.84,
    "I_load": 50.0, "T_cell": 30.0, "V_RC": 0.025,
    "state": "DISCHARGING", "fault_code": "NONE",
}


@pytest.fixture
async def mock_server_port():
    """Start a TCP server that sends 5 telemetry frames then closes."""
    async def _handler(reader, writer):
        for _ in range(5):
            writer.write((json.dumps(_FRAME) + "\n").encode())
            await writer.drain()
            await asyncio.sleep(0.01)
        writer.close()

    server = await asyncio.start_server(_handler, "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    async with server:
        yield port


async def test_connection_established(mock_server_port):
    client = OrchestratorClient("127.0.0.1", mock_server_port)
    await client.start()
    await asyncio.sleep(0.15)
    assert client.last_frame is not None
    await client.stop()


async def test_frame_parsed_correctly(mock_server_port):
    client = OrchestratorClient("127.0.0.1", mock_server_port)
    await client.start()
    await asyncio.sleep(0.15)
    frame = client.last_frame
    assert isinstance(frame, TelemetryFrame)
    assert frame.SoC == 0.8
    assert frame.state == "DISCHARGING"
    await client.stop()


async def test_command_sent_to_server():
    received: list[dict] = []

    async def _handler(reader, writer):
        writer.write((json.dumps(_FRAME) + "\n").encode())
        await writer.drain()
        try:
            line = await asyncio.wait_for(reader.readline(), timeout=1.0)
            received.append(json.loads(line))
        except asyncio.TimeoutError:
            pass
        writer.close()

    server = await asyncio.start_server(_handler, "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    async with server:
        client = OrchestratorClient("127.0.0.1", port)
        await client.start()
        await asyncio.sleep(0.1)
        await client.send_command("SET_CURRENT", 50.0)
        await asyncio.sleep(0.2)
        await client.stop()

    assert any(c.get("command") == "SET_CURRENT" for c in received)
