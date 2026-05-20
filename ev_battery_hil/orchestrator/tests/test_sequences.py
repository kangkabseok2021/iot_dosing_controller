import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from orchestrator.app.sequences import SequenceEngine, SequenceRun
from orchestrator.app.models import TelemetryFrame

_FRAME = TelemetryFrame(
    ts_us=1000, SoC=0.8, V_terminal=3.84,
    I_load=0.0, T_cell=25.0, V_RC=0.0,
    state="IDLE", fault_code="NONE",
)


@pytest.fixture
def mock_client():
    c = MagicMock()
    c.send_command = AsyncMock()
    c.last_frame = _FRAME
    return c


async def _run_seq(engine: SequenceEngine, seq_id: str) -> SequenceRun:
    """Run a sequence synchronously (asyncio.sleep mocked to no-op)."""
    spec = engine.load_sequence(seq_id)
    run = SequenceRun(seq_id=seq_id, running=True)
    with patch("orchestrator.app.sequences.asyncio.sleep", new_callable=AsyncMock):
        await engine._run(spec, run)
    return run


async def test_acceleration_pulse_sends_200A(mock_client):
    run = await _run_seq(SequenceEngine(mock_client), "ACCELERATION_PULSE")
    sent_currents = [
        c.args[1] for c in mock_client.send_command.call_args_list
        if c.args[0] == "SET_CURRENT"
    ]
    assert 200.0 in sent_currents


async def test_regen_braking_sends_negative_current(mock_client):
    run = await _run_seq(SequenceEngine(mock_client), "REGEN_BRAKING")
    sent_currents = [
        c.args[1] for c in mock_client.send_command.call_args_list
        if c.args[0] == "SET_CURRENT"
    ]
    assert any(v < 0 for v in sent_currents)


async def test_constant_discharge_sends_50A(mock_client):
    run = await _run_seq(SequenceEngine(mock_client), "CONSTANT_DISCHARGE")
    sent_currents = [
        c.args[1] for c in mock_client.send_command.call_args_list
        if c.args[0] == "SET_CURRENT"
    ]
    assert 50.0 in sent_currents


async def test_capacity_test_sends_20A(mock_client):
    run = await _run_seq(SequenceEngine(mock_client), "CAPACITY_TEST")
    sent_currents = [
        c.args[1] for c in mock_client.send_command.call_args_list
        if c.args[0] == "SET_CURRENT"
    ]
    assert 20.0 in sent_currents
