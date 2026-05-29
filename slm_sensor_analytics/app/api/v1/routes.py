from datetime import datetime, timezone, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.schemas import (
    AlertOut,
    IngestResponse,
    MeasurementCreate,
    PredictRequest,
    PredictResponse,
    TrainRequest,
    TrainResponse,
)
from app.config import settings
from app.db.models import Alert, Measurement
from app.db.session import get_db
from app.repositories import alert_repo, sensor_repo
from app.services.features import extract_features

router = APIRouter(prefix="/api/v1")


@router.post("/ingest", response_model=IngestResponse)
async def ingest_measurements(
    payload: list[MeasurementCreate], db: AsyncSession = Depends(get_db)
):
    db_items = [
        Measurement(
            device_id=item.device_id,
            sensor_type=item.sensor_type,
            value=item.value,
            unit=item.unit,
            recorded_at=item.recorded_at if item.recorded_at else datetime.now(timezone.utc),
        )
        for item in payload
    ]
    await sensor_repo.insert_readings(db, db_items)
    return IngestResponse(inserted=len(db_items))


@router.post("/train", response_model=TrainResponse)
async def train_model(
    request: Request, payload: TrainRequest, db: AsyncSession = Depends(get_db)
):
    readings = await sensor_repo.query_window(
        db, payload.device_id, payload.sensor_type, payload.start, payload.end
    )
    if len(readings) < payload.window_size:
        raise HTTPException(
            status_code=422,
            detail=f"Fewer readings ({len(readings)}) than window_size ({payload.window_size}).",
        )

    # Chunk into non-overlapping windows of window_size
    windows_values = []
    values = [r.value for r in readings]
    for i in range(0, len(values) - payload.window_size + 1, payload.window_size):
        windows_values.append(values[i : i + payload.window_size])

    if not windows_values:
        raise HTTPException(status_code=422, detail="Fewer readings than window_size.")

    # Extract features for each window
    X = []
    for w in windows_values:
        try:
            f_vec = extract_features(w)
            X.append(f_vec)
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e))

    # Fit the model and save
    model_store = request.app.state.model_store
    model_key = model_store.fit(payload.device_id, payload.sensor_type, X)

    return TrainResponse(windows_trained=len(X), model_key=model_key)


@router.post("/predict", response_model=PredictResponse)
async def predict_anomaly(
    request: Request, payload: PredictRequest, db: AsyncSession = Depends(get_db)
):
    now = datetime.now(timezone.utc)
    start = now - timedelta(minutes=payload.lookback_minutes)

    readings = await sensor_repo.query_window(
        db, payload.device_id, payload.sensor_type, start, now
    )

    if len(readings) < 2:
        raise HTTPException(
            status_code=422,
            detail=f"Fewer than 2 readings ({len(readings)}) found in lookback window.",
        )

    values = [r.value for r in readings]
    f_vec = extract_features(values)

    model_store = request.app.state.model_store
    try:
        score = model_store.predict(payload.device_id, payload.sensor_type, f_vec)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    is_anomaly = score < settings.ANOMALY_THRESHOLD
    alert_id = None

    if is_anomaly:
        feature_snapshot = {
            "mean": f_vec[0],
            "std": f_vec[1],
            "rms": f_vec[2],
            "peak_to_peak": f_vec[3],
            "kurtosis": f_vec[4],
        }
        alert = Alert(
            device_id=payload.device_id,
            sensor_type=payload.sensor_type,
            anomaly_score=score,
            threshold=settings.ANOMALY_THRESHOLD,
            feature_snapshot=feature_snapshot,
        )
        saved_alert = await alert_repo.insert_alert(db, alert)
        alert_id = saved_alert.id

    features_dict = {
        "mean": f_vec[0],
        "std": f_vec[1],
        "rms": f_vec[2],
        "peak_to_peak": f_vec[3],
        "kurtosis": f_vec[4],
    }

    return PredictResponse(
        anomaly_score=score,
        is_anomaly=is_anomaly,
        features=features_dict,
        alert_id=alert_id,
    )


@router.get("/alerts", response_model=list[AlertOut])
async def get_alerts(
    device_id: Optional[str] = None,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
):
    alerts = await alert_repo.list_alerts(db, device_id, limit)
    return alerts
