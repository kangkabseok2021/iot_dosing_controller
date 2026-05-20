import pytest
from pydantic import ValidationError
from orchestrator.app.models import TelemetryFrame, LoadCommand


def test_telemetry_frame_valid(sample_frame):
    assert sample_frame.SoC == 0.8
    assert sample_frame.state == "DISCHARGING"


def test_telemetry_soc_out_of_range_raises():
    with pytest.raises(ValidationError):
        TelemetryFrame(
            ts_us=1, SoC=1.5, V_terminal=3.8, I_load=50.0,
            T_cell=30.0, V_RC=0.0, state="IDLE", fault_code="NONE",
        )


def test_telemetry_tcell_out_of_range_raises():
    with pytest.raises(ValidationError):
        TelemetryFrame(
            ts_us=1, SoC=0.8, V_terminal=3.8, I_load=50.0,
            T_cell=200.0, V_RC=0.0, state="IDLE", fault_code="NONE",
        )


def test_load_command_invalid_literal_raises():
    with pytest.raises(ValidationError):
        LoadCommand(command="UNKNOWN_CMD", value=1.0)
