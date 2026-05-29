import pytest
import random
from datetime import datetime, timezone, timedelta
from httpx import AsyncClient
from app.db.models import Measurement
from app.main import app

def generate_train_data(now: datetime, count: int = 2000) -> list[Measurement]:
    rng = random.Random(42)
    return [
        Measurement(
            device_id="dev_01",
            sensor_type="temp",
            value=20.0 + rng.normalvariate(0, 0.1),
            unit="C",
            recorded_at=now - timedelta(minutes=600) + timedelta(seconds=i * 5)
        )
        for i in range(count)
    ]

@pytest.mark.asyncio
async def test_predict_no_model(client: AsyncClient, db_session):
    now = datetime.now(timezone.utc)
    # Ingest 2 readings
    m1 = Measurement(device_id="dev_01", sensor_type="temp", value=20.0, unit="C", recorded_at=now - timedelta(minutes=1))
    m2 = Measurement(device_id="dev_01", sensor_type="temp", value=21.0, unit="C", recorded_at=now - timedelta(seconds=10))
    db_session.add_all([m1, m2])
    await db_session.commit()

    payload = {
        "device_id": "dev_01",
        "sensor_type": "temp",
        "lookback_minutes": 10
    }
    response = await client.post("/api/v1/predict", json=payload)
    assert response.status_code == 422
    assert "No trained model found" in response.json()["detail"]

@pytest.mark.asyncio
async def test_predict_insufficient_readings(client: AsyncClient, db_session):
    # Train the model first
    now = datetime.now(timezone.utc)
    train_measurements = generate_train_data(now)
    db_session.add_all(train_measurements)
    await db_session.commit()

    # Train model
    train_payload = {
        "device_id": "dev_01",
        "sensor_type": "temp",
        "start": (now - timedelta(minutes=610)).isoformat(),
        "end": (now - timedelta(minutes=300)).isoformat(),
        "window_size": 10
    }
    train_res = await client.post("/api/v1/train", json=train_payload)
    assert train_res.status_code == 200

    # Ingest only 1 reading in the lookback window (from now - 10 minutes)
    m = Measurement(device_id="dev_01", sensor_type="temp", value=20.5, unit="C", recorded_at=now - timedelta(minutes=1))
    db_session.add(m)
    await db_session.commit()

    predict_payload = {
        "device_id": "dev_01",
        "sensor_type": "temp",
        "lookback_minutes": 10
    }
    response = await client.post("/api/v1/predict", json=predict_payload)
    assert response.status_code == 422
    assert "Fewer than 2 readings" in response.json()["detail"]

@pytest.mark.asyncio
async def test_predict_normal_case(client: AsyncClient, db_session):
    now = datetime.now(timezone.utc)
    # Train model with normal data
    train_measurements = generate_train_data(now)
    db_session.add_all(train_measurements)
    await db_session.commit()

    train_payload = {
        "device_id": "dev_01",
        "sensor_type": "temp",
        "start": (now - timedelta(minutes=610)).isoformat(),
        "end": (now - timedelta(minutes=300)).isoformat(),
        "window_size": 10
    }
    await client.post("/api/v1/train", json=train_payload)

    # Ingest 2 normal readings in lookback window
    m1 = Measurement(device_id="dev_01", sensor_type="temp", value=20.1, unit="C", recorded_at=now - timedelta(minutes=2))
    m2 = Measurement(device_id="dev_01", sensor_type="temp", value=20.2, unit="C", recorded_at=now - timedelta(minutes=1))
    db_session.add_all([m1, m2])
    await db_session.commit()

    predict_payload = {
        "device_id": "dev_01",
        "sensor_type": "temp",
        "lookback_minutes": 10
    }
    response = await client.post("/api/v1/predict", json=predict_payload)
    assert response.status_code == 200
    data = response.json()
    assert data["is_anomaly"] is False
    assert data["anomaly_score"] >= -0.1
    assert data["alert_id"] is None
    assert "mean" in data["features"]

@pytest.mark.asyncio
async def test_predict_anomaly_case_outlier(client: AsyncClient, db_session):
    now = datetime.now(timezone.utc)
    # Train model with normal data
    train_measurements = generate_train_data(now)
    db_session.add_all(train_measurements)
    await db_session.commit()

    train_payload = {
        "device_id": "dev_01",
        "sensor_type": "temp",
        "start": (now - timedelta(minutes=610)).isoformat(),
        "end": (now - timedelta(minutes=300)).isoformat(),
        "window_size": 10
    }
    await client.post("/api/v1/train", json=train_payload)

    # Ingest a severe outlier of 999.0 and a normal point in lookback window
    m1 = Measurement(device_id="dev_01", sensor_type="temp", value=999.0, unit="C", recorded_at=now - timedelta(minutes=2))
    m2 = Measurement(device_id="dev_01", sensor_type="temp", value=20.0, unit="C", recorded_at=now - timedelta(minutes=1))
    db_session.add_all([m1, m2])
    await db_session.commit()

    predict_payload = {
        "device_id": "dev_01",
        "sensor_type": "temp",
        "lookback_minutes": 10
    }
    response = await client.post("/api/v1/predict", json=predict_payload)
    assert response.status_code == 200
    data = response.json()
    assert data["is_anomaly"] is True
    assert data["anomaly_score"] < -0.1
    assert data["alert_id"] is not None

@pytest.mark.asyncio
async def test_predict_custom_lookback(client: AsyncClient, db_session):
    now = datetime.now(timezone.utc)
    train_measurements = generate_train_data(now)
    db_session.add_all(train_measurements)
    await db_session.commit()

    train_payload = {
        "device_id": "dev_01",
        "sensor_type": "temp",
        "start": (now - timedelta(minutes=610)).isoformat(),
        "end": (now - timedelta(minutes=300)).isoformat(),
        "window_size": 10
    }
    await client.post("/api/v1/train", json=train_payload)

    # Ingest readings 15 minutes ago, none in the last 10 minutes
    m1 = Measurement(device_id="dev_01", sensor_type="temp", value=20.1, unit="C", recorded_at=now - timedelta(minutes=16))
    m2 = Measurement(device_id="dev_01", sensor_type="temp", value=20.2, unit="C", recorded_at=now - timedelta(minutes=15))
    db_session.add_all([m1, m2])
    await db_session.commit()

    # Query with default 10 minutes lookback -> should fail (0 readings)
    payload_default = {
        "device_id": "dev_01",
        "sensor_type": "temp",
    }
    response_default = await client.post("/api/v1/predict", json=payload_default)
    assert response_default.status_code == 422
    assert "Fewer than 2 readings" in response_default.json()["detail"]

    # Query with custom 20 minutes lookback -> should succeed
    payload_custom = {
        "device_id": "dev_01",
        "sensor_type": "temp",
        "lookback_minutes": 20
    }
    response_custom = await client.post("/api/v1/predict", json=payload_custom)
    assert response_custom.status_code == 200
    assert response_custom.json()["is_anomaly"] is False
