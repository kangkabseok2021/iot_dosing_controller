from datetime import datetime
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.models import Measurement


async def insert_readings(session: AsyncSession, measurements: list[Measurement]) -> None:
    session.add_all(measurements)
    await session.commit()


async def query_window(
    session: AsyncSession,
    device_id: str,
    sensor_type: str,
    start: datetime,
    end: datetime,
) -> list[Measurement]:
    stmt = (
        select(Measurement)
        .where(
            Measurement.device_id == device_id,
            Measurement.sensor_type == sensor_type,
            Measurement.recorded_at >= start,
            Measurement.recorded_at <= end,
        )
        .order_by(Measurement.recorded_at.asc())
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def query_recent(
    session: AsyncSession,
    device_id: str,
    sensor_type: str,
    limit: int,
) -> list[Measurement]:
    stmt = (
        select(Measurement)
        .where(
            Measurement.device_id == device_id,
            Measurement.sensor_type == sensor_type,
        )
        .order_by(Measurement.recorded_at.desc())
        .limit(limit)
    )
    result = await session.execute(stmt)
    readings = list(result.scalars().all())
    # Return in chronological order
    readings.reverse()
    return readings
