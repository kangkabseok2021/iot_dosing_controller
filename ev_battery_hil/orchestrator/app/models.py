from typing import Literal

from pydantic import BaseModel, Field


class TelemetryFrame(BaseModel):
    ts_us: int
    SoC: float = Field(..., ge=0, le=1)
    V_terminal: float = Field(..., ge=0, le=4.2)
    I_load: float
    T_cell: float = Field(..., ge=-40, le=150)
    V_RC: float
    state: str
    fault_code: str


class LoadCommand(BaseModel):
    command: Literal["SET_CURRENT", "SET_MODE", "RESET", "SET_FAULT"]
    value: str | float | None = None


class FaultRequest(BaseModel):
    fault_type: Literal["THERMAL_RUNAWAY", "SENSOR_DROPOUT", "OVERCURRENT"]
    params: dict | None = None
