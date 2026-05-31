from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

_VALID_UNITS = Literal["bar", "°C", "rpm", "V", "A", "kPa", "Hz"]


class SensorEventCreate(BaseModel):
    plant_id: str = Field(min_length=1, max_length=64)
    sensor_id: str = Field(min_length=1, max_length=64)
    timestamp: datetime
    value: float
    unit: _VALID_UNITS


class SensorEventResponse(BaseModel):
    id: UUID
    plant_id: str
    sensor_id: str
    timestamp: datetime
    value: float
    unit: str
    created_at: datetime
    raw_s3_key: str | None

    model_config = {"from_attributes": True}


class PaginatedEvents(BaseModel):
    items: list[SensorEventResponse]
    total: int
    limit: int
    offset: int
