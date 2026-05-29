import pytest
from datetime import datetime, timezone, timedelta
from httpx import AsyncClient
from app.db.models import Measurement

@pytest.mark.asyncio
async def test_train_model_success(client: AsyncClient, db_session):
    now = datetime.now(timezone.utc)
    # Ingest 20 measurements (2 windows of size 10)
    measurements = []
    for i in range(20):
        measurements.append(
            Measurement(
                device_id="device_01",
                sensor_type="temperature",
                value=20.0 + (i % 3),
                unit="C",
                recorded_at=now - timedelta(minutes=25 - i)
            )
        )
    db_session.add_all(measurements)
    await db_session.commit()

    payload = {
        "device_id": "device_01",
        "sensor_type": "temperature",
        "start": (now - timedelta(minutes=30)).isoformat(),
        "end": (now + timedelta(minutes=5)).isoformat(),
        "window_size": 10
    }
    
    response = await client.post("/api/v1/train", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["windows_trained"] == 2
    assert data["model_key"] == "device_01__temperature"

@pytest.mark.asyncio
async def test_train_model_insufficient_readings(client: AsyncClient, db_session):
    now = datetime.now(timezone.utc)
    # Ingest only 5 measurements, but window_size is 10
    measurements = []
    for i in range(5):
        measurements.append(
            Measurement(
                device_id="device_01",
                sensor_type="temperature",
                value=20.0,
                unit="C",
                recorded_at=now - timedelta(minutes=10 - i)
            )
        )
    db_session.add_all(measurements)
    await db_session.commit()

    payload = {
        "device_id": "device_01",
        "sensor_type": "temperature",
        "start": (now - timedelta(minutes=15)).isoformat(),
        "end": (now + timedelta(minutes=5)).isoformat(),
        "window_size": 10
    }
    
    response = await client.post("/api/v1/train", json=payload)
    assert response.status_code == 422
    assert "Fewer readings" in response.json()["detail"]

@pytest.mark.asyncio
async def test_train_model_empty_range(client: AsyncClient):
    # No readings in the database for the given range
    now = datetime.now(timezone.utc)
    payload = {
        "device_id": "device_02",
        "sensor_type": "temperature",
        "start": (now - timedelta(minutes=30)).isoformat(),
        "end": (now + timedelta(minutes=5)).isoformat(),
        "window_size": 10
    }
    response = await client.post("/api/v1/train", json=payload)
    assert response.status_code == 422
    assert "Fewer readings" in response.json()["detail"]
