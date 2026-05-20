from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from orchestrator.app.client import OrchestratorClient
from orchestrator.app.fault_injector import FaultInjector


@pytest.fixture
def mock_client():
    c = MagicMock(spec=OrchestratorClient)
    c.send_command = AsyncMock()
    c.disconnect = AsyncMock()
    return c


async def test_thermal_runaway_sends_set_fault(mock_client):
    injector = FaultInjector(mock_client)
    await injector.inject("THERMAL_RUNAWAY")
    mock_client.send_command.assert_awaited_once_with("SET_FAULT", "THERMAL_RUNAWAY")


async def test_overcurrent_sends_300A(mock_client):
    injector = FaultInjector(mock_client)
    await injector.inject("OVERCURRENT")
    mock_client.send_command.assert_awaited_once_with("SET_CURRENT", 300.0)


async def test_sensor_dropout_calls_disconnect(mock_client):
    injector = FaultInjector(mock_client)
    with patch("orchestrator.app.fault_injector.asyncio.sleep", new_callable=AsyncMock):
        await injector.inject("SENSOR_DROPOUT", {"duration_s": 0.1})
    mock_client.disconnect.assert_awaited_once()


async def test_unknown_fault_raises(mock_client):
    injector = FaultInjector(mock_client)
    with pytest.raises(ValueError, match="Unknown fault type"):
        await injector.inject("MADE_UP_FAULT")
