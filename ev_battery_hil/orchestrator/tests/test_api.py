from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from orchestrator.app.main import app
from orchestrator.app.models import TelemetryFrame

_FRAME = TelemetryFrame(
    ts_us=1_000_000,
    SoC=0.8,
    V_terminal=3.84,
    I_load=50.0,
    T_cell=30.0,
    V_RC=0.025,
    state="DISCHARGING",
    fault_code="NONE",
)


@pytest.fixture
async def api_client(monkeypatch):
    import orchestrator.app.main as m

    mock_c = MagicMock()
    mock_c.last_frame = _FRAME
    mock_c.send_command = AsyncMock()
    mock_c.start = AsyncMock()
    mock_c.stop = AsyncMock()

    mock_e = MagicMock()
    mock_e.start = AsyncMock()
    mock_e.status.return_value = None

    mock_i = MagicMock()
    mock_i.inject = AsyncMock()

    # Patch module globals directly so the lifespan picks them up
    monkeypatch.setattr(m, "client", mock_c)
    monkeypatch.setattr(m, "engine", mock_e)
    monkeypatch.setattr(m, "injector", mock_i)
    # Also patch constructors so lifespan re-assignment uses mocks
    monkeypatch.setattr("orchestrator.app.main.OrchestratorClient", lambda *a, **kw: mock_c)
    monkeypatch.setattr("orchestrator.app.main.SequenceEngine", lambda *a, **kw: mock_e)
    monkeypatch.setattr("orchestrator.app.main.FaultInjector", lambda *a, **kw: mock_i)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


async def test_get_status_200(api_client):
    r = await api_client.get("/api/status")
    assert r.status_code == 200
    assert r.json()["SoC"] == 0.8


async def test_post_command_200(api_client):
    r = await api_client.post("/api/command", json={"command": "SET_CURRENT", "value": 50.0})
    assert r.status_code == 200
    assert r.json()["ok"] is True


async def test_post_faults_inject_200(api_client):
    r = await api_client.post("/api/faults/inject", json={"fault_type": "THERMAL_RUNAWAY"})
    assert r.status_code == 200
    assert r.json()["injected"] == "THERMAL_RUNAWAY"


async def test_sequence_status_404_for_unknown(api_client):
    r = await api_client.get("/api/sequences/NO_SUCH_SEQ/status")
    assert r.status_code == 404
