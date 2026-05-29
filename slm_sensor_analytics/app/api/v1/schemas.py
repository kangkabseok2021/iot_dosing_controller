from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel


class MeasurementCreate(BaseModel):
    device_id: str
    sensor_type: str
    value: float
    unit: str
    recorded_at: Optional[datetime] = None


class IngestResponse(BaseModel):
    inserted: int


class TrainRequest(BaseModel):
    device_id: str
    sensor_type: str
    start: datetime
    end: datetime
    window_size: int = 10


class TrainResponse(BaseModel):
    windows_trained: int
    model_key: str


class PredictRequest(BaseModel):
    device_id: str
    sensor_type: str
    lookback_minutes: int = 10


class PredictResponse(BaseModel):
    anomaly_score: float
    is_anomaly: bool
    features: dict[str, float]
    alert_id: Optional[int] = None


class AlertOut(BaseModel):
    id: int
    device_id: str
    sensor_type: str
    anomaly_score: float
    threshold: float
    triggered_at: datetime
    feature_snapshot: dict[str, Any]

    model_config = {"from_attributes": True}
