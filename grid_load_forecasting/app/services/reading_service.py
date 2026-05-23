from datetime import datetime, timezone

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import LoadReading as LoadReadingORM
from app.db.models import Node, NodeForecast
from app.models.reading import LoadReading as LoadReadingSchema
from app.models.reading import NodeSummary, ReadingResponse


class ReadingService:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def ensure_node(self, node_id: str, meter_type: str) -> None:
        result = await self._session.get(Node, node_id)
        if result is None:
            self._session.add(Node(node_id=node_id, meter_type=meter_type))
            await self._session.flush()

    async def ingest(self, reading: LoadReadingSchema) -> ReadingResponse:
        await self.ensure_node(reading.node_id, reading.meter_type or "residential")
        ts = reading.timestamp if reading.timestamp.tzinfo else reading.timestamp.replace(
            tzinfo=timezone.utc
        )
        orm = LoadReadingORM(
            node_id=reading.node_id,
            ts=ts,
            kwh=reading.kwh,
            meter_type=reading.meter_type or "residential",
            accepted_at=datetime.now(tz=timezone.utc),
        )
        self._session.add(orm)
        await self._session.flush()
        await self._session.refresh(orm)
        return ReadingResponse(
            id=orm.id,
            node_id=orm.node_id,
            timestamp=orm.ts,
            kwh=orm.kwh,
            accepted_at=orm.accepted_at,
        )

    async def get_recent(
        self,
        node_id: str,
        limit: int = 96,
        from_ts: datetime | None = None,
        to_ts: datetime | None = None,
        offset: int = 0,
    ) -> list[LoadReadingORM]:
        stmt = (
            select(LoadReadingORM)
            .where(LoadReadingORM.node_id == node_id)
            .order_by(desc(LoadReadingORM.ts))
            .limit(limit)
            .offset(offset)
        )
        if from_ts:
            stmt = stmt.where(LoadReadingORM.ts >= from_ts)
        if to_ts:
            stmt = stmt.where(LoadReadingORM.ts <= to_ts)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_node_summaries(self) -> list[NodeSummary]:
        stmt = select(
            LoadReadingORM.node_id,
            func.count(LoadReadingORM.id).label("reading_count"),
            func.max(LoadReadingORM.ts).label("latest_ts"),
            func.avg(LoadReadingORM.kwh).label("current_kwh"),
        ).group_by(LoadReadingORM.node_id)
        result = await self._session.execute(stmt)
        return [
            NodeSummary(
                node_id=row.node_id,
                reading_count=row.reading_count,
                latest_ts=row.latest_ts,
                current_kwh=row.current_kwh,
            )
            for row in result
        ]

    async def upsert_forecast(
        self, node_id: str, forecast_kwh: float, window_size: int
    ) -> None:
        existing = await self._session.get(NodeForecast, node_id)
        now = datetime.now(tz=timezone.utc)
        if existing:
            existing.forecast_kwh = forecast_kwh
            existing.computed_at = now
            existing.window_size = window_size
        else:
            self._session.add(
                NodeForecast(
                    node_id=node_id,
                    forecast_kwh=forecast_kwh,
                    computed_at=now,
                    window_size=window_size,
                )
            )
        await self._session.flush()

    async def get_forecast(self, node_id: str) -> NodeForecast | None:
        return await self._session.get(NodeForecast, node_id)
