"""5 tests for EventRepository."""

from datetime import datetime, timezone

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.repository import EventRepository
from app.schemas import SensorEventCreate


def _payload(**overrides) -> SensorEventCreate:
    return SensorEventCreate(
        **{
            "plant_id": "PLT-001",
            "sensor_id": "TEMP-A",
            "timestamp": datetime(2026, 1, 15, 8, 0, tzinfo=timezone.utc),
            "value": 85.3,
            "unit": "°C",
        }
        | overrides
    )


async def test_insert_and_retrieve_by_id(db_session: AsyncSession):
    repo = EventRepository(db_session)
    event = await repo.insert(_payload())
    fetched = await repo.get_by_id(event.id)
    assert fetched is not None
    assert fetched.plant_id == "PLT-001"
    assert fetched.value == pytest.approx(85.3)


async def test_list_filter_by_plant_id(db_session: AsyncSession):
    repo = EventRepository(db_session)
    await repo.insert(_payload(plant_id="PLT-001"))
    await repo.insert(_payload(plant_id="PLT-002"))
    items, total = await repo.list_events(plant_id="PLT-001")
    assert total == 1
    assert items[0].plant_id == "PLT-001"


async def test_list_pagination_total_count(db_session: AsyncSession):
    repo = EventRepository(db_session)
    for i in range(5):
        await repo.insert(_payload(sensor_id=f"SENS-{i}"))
    items, total = await repo.list_events(limit=2, offset=0)
    assert total == 5
    assert len(items) == 2


async def test_set_s3_key_persists(db_session: AsyncSession):
    repo = EventRepository(db_session)
    event = await repo.insert(_payload())
    await repo.set_s3_key(event.id, "events/2026-01-15/PLT-001/abc.json")
    fetched = await repo.get_by_id(event.id)
    assert fetched is not None
    assert fetched.raw_s3_key == "events/2026-01-15/PLT-001/abc.json"


async def test_get_by_id_missing_returns_none(db_session: AsyncSession):
    from uuid import uuid4

    repo = EventRepository(db_session)
    result = await repo.get_by_id(uuid4())
    assert result is None
