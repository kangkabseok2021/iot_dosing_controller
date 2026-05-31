from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Annotated
from uuid import UUID

from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import JSONResponse
from prometheus_client import make_asgi_app
from sqlalchemy.ext.asyncio import AsyncSession

from app.archival import S3Archiver
from app.db.session import get_session
from app.repository import EventRepository
from app.schemas import PaginatedEvents, SensorEventCreate, SensorEventResponse

logger = logging.getLogger(__name__)

_archiver = S3Archiver()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("AWS Sensor API starting")
    yield
    logger.info("AWS Sensor API shutdown")


app = FastAPI(
    title="AWS Sensor API",
    description="Cloud-native OEM sensor ingestion — ECS Fargate + RDS + S3",
    version="0.1.0",
    lifespan=lifespan,
)

app.mount("/metrics", make_asgi_app())

SessionDep = Annotated[AsyncSession, Depends(get_session)]


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@app.post("/api/v1/events", status_code=201, response_model=SensorEventResponse)
async def create_event(payload: SensorEventCreate, session: SessionDep) -> SensorEventResponse:
    repo = EventRepository(session)
    event = await repo.insert(payload)
    # Fire-and-forget S3 archival — does not block response
    asyncio.create_task(
        _archive_and_update(str(event.id), payload.plant_id, payload.model_dump(), repo)
    )
    return SensorEventResponse.model_validate(event)


async def _archive_and_update(
    event_id: str, plant_id: str, payload: dict, repo: EventRepository
) -> None:
    key = await _archiver.archive(event_id, plant_id, payload)
    if key:
        from uuid import UUID as _UUID

        await repo.set_s3_key(_UUID(event_id), key)


@app.get("/api/v1/events", response_model=PaginatedEvents)
async def list_events(
    session: SessionDep,
    plant_id: str | None = None,
    sensor_id: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> PaginatedEvents:
    repo = EventRepository(session)
    items, total = await repo.list_events(plant_id, sensor_id, limit, offset)
    return PaginatedEvents(
        items=[SensorEventResponse.model_validate(e) for e in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@app.get("/api/v1/events/{event_id}", response_model=SensorEventResponse)
async def get_event(event_id: UUID, session: SessionDep) -> SensorEventResponse:
    repo = EventRepository(session)
    event = await repo.get_by_id(event_id)
    if event is None:
        raise HTTPException(status_code=404, detail=f"Event '{event_id}' not found")
    return SensorEventResponse.model_validate(event)
