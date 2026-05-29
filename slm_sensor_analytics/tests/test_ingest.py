import pytest
from httpx import AsyncClient
from sqlalchemy import select
from app.db.models import Measurement

@pytest.mark.asyncio
async def test_ingest_single_payload(client: AsyncClient, db_session):
    payload = [
        {
            "device_id": "device_01",
            "sensor_type": "temperature",
            "value": 23.5,
            "unit": "C"
        }
    ]
    response = await client.post("/api/v1/ingest", json=payload)
    assert response.status_code == 200
    assert response.json() == {"inserted": 1}

    # Verify db
    result = await db_session.execute(select(Measurement).where(Measurement.device_id == "device_01"))
    measurements = result.scalars().all()
    assert len(measurements) == 1
    assert measurements[0].value == 23.5
    assert measurements[0].sensor_type == "temperature"

@pytest.mark.asyncio
async def test_ingest_bulk_payload(client: AsyncClient, db_session):
    payload = [
        {
            "device_id": "device_01",
            "sensor_type": "temperature",
            "value": 24.0,
            "unit": "C"
        },
        {
            "device_id": "device_01",
            "sensor_type": "vibration",
            "value": 0.05,
            "unit": "g"
        }
    ]
    response = await client.post("/api/v1/ingest", json=payload)
    assert response.status_code == 200
    assert response.json() == {"inserted": 2}

    # Verify db
    result = await db_session.execute(select(Measurement).where(Measurement.device_id == "device_01"))
    measurements = result.scalars().all()
    assert len(measurements) == 2

@pytest.mark.asyncio
async def test_ingest_validation_missing_fields(client: AsyncClient):
    # Missing device_id
    payload = [
        {
            "sensor_type": "temperature",
            "value": 23.5,
            "unit": "C"
        }
    ]
    response = await client.post("/api/v1/ingest", json=payload)
    assert response.status_code == 422

@pytest.mark.asyncio
async def test_ingest_validation_invalid_types(client: AsyncClient):
    # value is not a float
    payload = [
        {
            "device_id": "device_01",
            "sensor_type": "temperature",
            "value": "high",
            "unit": "C"
        }
    ]
    response = await client.post("/api/v1/ingest", json=payload)
    assert response.status_code == 422
