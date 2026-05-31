from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import SensorEvent
from app.schemas import SensorEventCreate


class EventRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def insert(self, payload: SensorEventCreate) -> SensorEvent:
        event = SensorEvent(
            plant_id=payload.plant_id,
            sensor_id=payload.sensor_id,
            timestamp=payload.timestamp,
            value=payload.value,
            unit=payload.unit,
        )
        self._session.add(event)
        await self._session.commit()
        await self._session.refresh(event)
        return event

    async def get_by_id(self, event_id: UUID) -> SensorEvent | None:
        result = await self._session.execute(
            select(SensorEvent).where(SensorEvent.id == event_id)
        )
        return result.scalar_one_or_none()

    async def list_events(
        self,
        plant_id: str | None = None,
        sensor_id: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[SensorEvent], int]:
        stmt = select(SensorEvent)
        count_stmt = select(func.count()).select_from(SensorEvent)
        if plant_id:
            stmt = stmt.where(SensorEvent.plant_id == plant_id)
            count_stmt = count_stmt.where(SensorEvent.plant_id == plant_id)
        if sensor_id:
            stmt = stmt.where(SensorEvent.sensor_id == sensor_id)
            count_stmt = count_stmt.where(SensorEvent.sensor_id == sensor_id)
        stmt = stmt.order_by(SensorEvent.timestamp.desc()).limit(limit).offset(offset)
        rows = (await self._session.execute(stmt)).scalars().all()
        total = (await self._session.execute(count_stmt)).scalar_one()
        return list(rows), total

    async def set_s3_key(self, event_id: UUID, s3_key: str) -> None:
        await self._session.execute(
            update(SensorEvent).where(SensorEvent.id == event_id).values(raw_s3_key=s3_key)
        )
        await self._session.commit()
