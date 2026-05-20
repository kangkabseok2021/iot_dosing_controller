import pytest

from orchestrator.app.models import TelemetryFrame


@pytest.fixture
def sample_frame() -> TelemetryFrame:
    return TelemetryFrame(
        ts_us=1_000_000,
        SoC=0.8,
        V_terminal=3.84,
        I_load=50.0,
        T_cell=30.0,
        V_RC=0.025,
        state="DISCHARGING",
        fault_code="NONE",
    )
