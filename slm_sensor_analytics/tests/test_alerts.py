import pytest
from datetime import datetime, timezone, timedelta
from httpx import AsyncClient
from app.db.models import Alert

@pytest.mark.asyncio
async def test_alerts_listing_empty(client: AsyncClient):
    response = await client.get("/api/v1/alerts")
    assert response.status_code == 200
    assert response.json() == []

@pytest.mark.asyncio
async def test_alerts_listing_populated(client: AsyncClient, db_session):
    now = datetime.now(timezone.utc)
    a1 = Alert(
        device_id="device_01",
        sensor_type="temp",
        anomaly_score=-0.15,
        threshold=-0.1,
        triggered_at=now - timedelta(minutes=5),
        feature_snapshot={"mean": 20.0, "std": 1.0, "rms": 20.0, "peak_to_peak": 2.0, "kurtosis": 0.0}
    )
    a2 = Alert(
        device_id="device_01",
        sensor_type="vibration",
        anomaly_score=-0.2,
        threshold=-0.1,
        triggered_at=now,
        feature_snapshot={"mean": 0.05, "std": 0.01, "rms": 0.05, "peak_to_peak": 0.02, "kurtosis": 0.0}
    )
    db_session.add_all([a1, a2])
    await db_session.commit()

    response = await client.get("/api/v1/alerts")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    # Verify descending ordering by triggered_at (a2 triggered at `now` is first)
    assert data[0]["sensor_type"] == "vibration"
    assert data[1]["sensor_type"] == "temp"

@pytest.mark.asyncio
async def test_alerts_filtering_by_device(client: AsyncClient, db_session):
    now = datetime.now(timezone.utc)
    a1 = Alert(
        device_id="device_01",
        sensor_type="temp",
        anomaly_score=-0.15,
        threshold=-0.1,
        triggered_at=now - timedelta(minutes=5),
        feature_snapshot={"mean": 20.0, "std": 1.0, "rms": 20.0, "peak_to_peak": 2.0, "kurtosis": 0.0}
    )
    a2 = Alert(
        device_id="device_02",
        sensor_type="temp",
        anomaly_score=-0.25,
        threshold=-0.1,
        triggered_at=now,
        feature_snapshot={"mean": 21.0, "std": 1.1, "rms": 21.0, "peak_to_peak": 2.1, "kurtosis": 0.0}
    )
    db_session.add_all([a1, a2])
    await db_session.commit()

    response = await client.get("/api/v1/alerts?device_id=device_01")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["device_id"] == "device_01"
    assert data[0]["anomaly_score"] == -0.15
