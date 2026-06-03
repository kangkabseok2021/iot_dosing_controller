from datetime import date, datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator


class AssetCreate(BaseModel):
    name: str
    type: Literal["wind", "solar"]
    capacity_mw: Annotated[float, Field(gt=0)]
    ramp_rate_mw_per_min: Annotated[float, Field(gt=0)] = 999.0


class AssetRead(AssetCreate):
    id: int
    model_config = {"from_attributes": True}


class TelemetryRow(BaseModel):
    asset_id: int
    measured_at: datetime
    power_mw: float

    @model_validator(mode="after")
    def power_non_negative(self) -> "TelemetryRow":
        if self.power_mw < 0:
            raise ValueError("power_mw must be >= 0")
        return self


class TelemetryBulk(BaseModel):
    rows: list[TelemetryRow] = Field(max_length=200)


class ForecastIntervalRead(BaseModel):
    interval_start: datetime
    interval_end: datetime
    mean_mw: float
    std_mw: float
    model_config = {"from_attributes": True}


class ForecastRunRead(BaseModel):
    run_id: int
    asset_id: int
    created_at: datetime
    mape: float
    intervals: list[ForecastIntervalRead] = []
    model_config = {"from_attributes": True}


# ── Fahrplan ──────────────────────────────────────────────────────────────────

ScheduleStatusLiteral = Literal["DRAFT", "SUBMITTED", "ACTIVE", "SUPERSEDED"]


class ScheduleInterval(BaseModel):
    asset_id: int
    interval_start: datetime
    interval_end: datetime
    scheduled_mw: Annotated[float, Field(ge=0)]
    status: ScheduleStatusLiteral = "DRAFT"

    @model_validator(mode="after")
    def validate_interval_duration(self) -> "ScheduleInterval":
        delta = self.interval_end - self.interval_start
        if abs(delta.total_seconds() - 3600) > 1:
            raise ValueError("interval duration must be exactly 1 hour")
        return self


class Fahrplan(BaseModel):
    schedule_id: UUID
    portfolio_id: int
    date: date
    created_at: datetime
    intervals: list[ScheduleInterval]


class OptimiseRequest(BaseModel):
    portfolio_id: int
    date: date
    asset_ids: list[int]
    price_curve_eur_mwh: list[float] = Field(min_length=1, max_length=96)


class FahrplanPatch(BaseModel):
    intervals: list[ScheduleInterval] | None = None
    status: ScheduleStatusLiteral | None = None
