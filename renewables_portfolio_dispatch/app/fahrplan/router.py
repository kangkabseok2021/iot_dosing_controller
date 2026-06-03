import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.fahrplan.blob_store import BlobStore, get_blob_store
from app.models.orm import Schedule, ScheduleIntervalDB
from app.models.schemas import Fahrplan, FahrplanPatch, ScheduleInterval

router = APIRouter(prefix="/api/fahrplan", tags=["fahrplan"])


@router.post("", response_model=Fahrplan, status_code=201)
async def create_fahrplan(
    body: Fahrplan,
    db: AsyncSession = Depends(get_db),
    blob: BlobStore = Depends(get_blob_store),
) -> Fahrplan:
    # Persist (upsert by schedule_id)
    schedule = Schedule(
        id=str(body.schedule_id),
        portfolio_id=body.portfolio_id,
        date=body.date.isoformat(),
        created_at=body.created_at,
    )
    db.add(schedule)
    await db.flush()

    for ivl in body.intervals:
        db.add(
            ScheduleIntervalDB(
                schedule_id=str(body.schedule_id),
                asset_id=ivl.asset_id,
                interval_start=ivl.interval_start,
                interval_end=ivl.interval_end,
                scheduled_mw=ivl.scheduled_mw,
                status=ivl.status,
            )
        )
    await db.commit()
    await blob.archive(body)
    return body


@router.get("/{schedule_id}", response_model=Fahrplan)
async def get_fahrplan(schedule_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> Fahrplan:
    result = await db.execute(select(Schedule).where(Schedule.id == str(schedule_id)))
    schedule = result.scalar_one_or_none()
    if schedule is None:
        raise HTTPException(status_code=404, detail="Schedule not found")

    ivl_result = await db.execute(
        select(ScheduleIntervalDB).where(ScheduleIntervalDB.schedule_id == str(schedule_id))
    )
    intervals = [
        ScheduleInterval(
            asset_id=i.asset_id,
            interval_start=i.interval_start,
            interval_end=i.interval_end,
            scheduled_mw=i.scheduled_mw,
            status=i.status,  # type: ignore[arg-type]
        )
        for i in ivl_result.scalars()
    ]
    from datetime import date

    return Fahrplan(
        schedule_id=schedule_id,
        portfolio_id=schedule.portfolio_id,
        date=date.fromisoformat(schedule.date),
        created_at=schedule.created_at,
        intervals=intervals,
    )


@router.patch("/{schedule_id}", response_model=Fahrplan)
async def patch_fahrplan(
    schedule_id: uuid.UUID,
    patch: FahrplanPatch,
    db: AsyncSession = Depends(get_db),
) -> Fahrplan:
    result = await db.execute(select(Schedule).where(Schedule.id == str(schedule_id)))
    schedule = result.scalar_one_or_none()
    if schedule is None:
        raise HTTPException(status_code=404, detail="Schedule not found")

    if patch.status is not None:
        ivl_result = await db.execute(
            select(ScheduleIntervalDB).where(ScheduleIntervalDB.schedule_id == str(schedule_id))
        )
        for ivl in ivl_result.scalars():
            ivl.status = patch.status

    if patch.intervals is not None:
        ivl_result = await db.execute(
            select(ScheduleIntervalDB).where(ScheduleIntervalDB.schedule_id == str(schedule_id))
        )
        existing = {i.id: i for i in ivl_result.scalars()}
        for new_ivl in patch.intervals:
            for db_ivl in existing.values():
                if db_ivl.asset_id == new_ivl.asset_id:
                    db_ivl.scheduled_mw = new_ivl.scheduled_mw
                    db_ivl.status = new_ivl.status

    await db.commit()
    return await get_fahrplan(schedule_id, db)
