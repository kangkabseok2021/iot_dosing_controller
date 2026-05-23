from datetime import datetime, timezone
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class LoadReading(BaseModel):
    node_id: str = Field(min_length=3, max_length=32, pattern=r"^[A-Z0-9_-]+$")
    timestamp: datetime
    kwh: float = Field(gt=0, le=10000)
    meter_type: Optional[Literal["residential", "industrial", "commercial"]] = "residential"

    model_config = ConfigDict(frozen=True, str_strip_whitespace=True)

    @field_validator("timestamp")
    @classmethod
    def no_future_timestamp(cls, v: datetime) -> datetime:
        now = datetime.now(tz=timezone.utc)
        ts = v if v.tzinfo else v.replace(tzinfo=timezone.utc)
        if (ts - now).total_seconds() > 60:
            raise ValueError("timestamp must not be more than 60 seconds in the future")
        return ts

    @field_validator("kwh")
    @classmethod
    def flag_implausible(cls, v: float) -> float:
        return v

    @model_validator(mode="after")
    def validate_kwh_for_meter_type(self) -> "LoadReading":
        caps = {"residential": 50.0, "commercial": 500.0, "industrial": 10000.0}
        cap = caps.get(self.meter_type or "residential", 10000.0)
        if self.kwh > cap:
            raise ValueError(
                f"kwh={self.kwh} exceeds cap {cap} kWh/interval for meter_type={self.meter_type}"
            )
        return self


class LoadReadingBatch(BaseModel):
    readings: list[LoadReading] = Field(max_length=1000)

    model_config = ConfigDict(frozen=True)


class ReadingResponse(BaseModel):
    id: int
    node_id: str
    timestamp: datetime
    kwh: float
    accepted_at: datetime


class NodeSummary(BaseModel):
    node_id: str
    reading_count: int
    latest_ts: Optional[datetime]
    current_kwh: Optional[float]


class AnomalyFlag(BaseModel):
    ts: datetime
    kwh: float
    zscore: float


class ForecastResponse(BaseModel):
    node_id: str
    forecast_kwh: Optional[float]
    computed_at: Optional[datetime]
    window_size: int
    confidence: Literal["low", "medium", "high"]
    raw_readings: list[dict]
    anomaly_flags: list[AnomalyFlag]
    horizon: list[dict]
