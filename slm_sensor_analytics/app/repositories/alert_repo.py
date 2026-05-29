from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.models import Alert


async def insert_alert(session: AsyncSession, alert: Alert) -> Alert:
    session.add(alert)
    await session.commit()
    await session.refresh(alert)
    return alert


async def list_alerts(
    session: AsyncSession,
    device_id: str | None = None,
    limit: int = 100,
) -> list[Alert]:
    stmt = select(Alert)
    if device_id is not None:
        stmt = stmt.where(Alert.device_id == device_id)
    stmt = stmt.order_by(Alert.triggered_at.desc()).limit(limit)
    result = await session.execute(stmt)
    return list(result.scalars().all())
