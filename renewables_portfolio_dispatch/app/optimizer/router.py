import uuid
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.orm import Asset, ForecastInterval, ForecastRun, Schedule, ScheduleIntervalDB
from app.models.schemas import Fahrplan, OptimiseRequest, ScheduleInterval
from app.optimizer.dispatch import AssetSpec, DispatchOptimiser

router = APIRouter(prefix="/api/schedule", tags=["optimizer"])


@router.post("/optimise", response_model=Fahrplan, status_code=201)
async def optimise_schedule(body: OptimiseRequest, db: AsyncSession = Depends(get_db)) -> Fahrplan:
    # Fetch assets
    assets_result = await db.execute(select(Asset).where(Asset.id.in_(body.asset_ids)))
    assets = assets_result.scalars().all()
    if len(assets) != len(body.asset_ids):
        raise HTTPException(status_code=404, detail="One or more assets not found")

    # Fetch latest forecasts
    T = len(body.price_curve_eur_mwh)
    forecasts: list[list[float]] = []
    for asset in assets:
        run_result = await db.execute(
            select(ForecastRun)
            .where(ForecastRun.asset_id == asset.id)
            .order_by(ForecastRun.created_at.desc())
            .limit(1)
        )
        run = run_result.scalar_one_or_none()
        if run:
            ivl_result = await db.execute(
                select(ForecastInterval)
                .where(ForecastInterval.run_id == run.id)
                .order_by(ForecastInterval.interval_start)
                .limit(T)
            )
            ivls = ivl_result.scalars().all()
            mus = [i.mean_mw for i in ivls]
            # Pad to T if fewer intervals returned
            mus += [0.0] * (T - len(mus))
        else:
            mus = [0.0] * T
        forecasts.append(mus[:T])

    specs = [AssetSpec(a.id, a.capacity_mw, a.ramp_rate_mw_per_min) for a in assets]

    try:
        result = DispatchOptimiser().optimise(specs, body.price_curve_eur_mwh, forecasts)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    # Persist schedule
    schedule_id = uuid.uuid4()
    now = datetime.now(UTC)
    t0 = datetime(body.date.year, body.date.month, body.date.day, tzinfo=UTC)

    schedule_db = Schedule(
        id=str(schedule_id),
        portfolio_id=body.portfolio_id,
        date=body.date.isoformat(),
        created_at=now,
    )
    db.add(schedule_db)
    await db.flush()

    intervals: list[ScheduleInterval] = []
    for i, asset in enumerate(assets):
        for t in range(T):
            start = t0 + timedelta(hours=t)
            end = start + timedelta(hours=1)
            mw = float(result.schedule_per_asset[i][t])
            db.add(
                ScheduleIntervalDB(
                    schedule_id=str(schedule_id),
                    asset_id=asset.id,
                    interval_start=start,
                    interval_end=end,
                    scheduled_mw=mw,
                    status="DRAFT",
                )
            )
            intervals.append(
                ScheduleInterval(
                    asset_id=asset.id,
                    interval_start=start,
                    interval_end=end,
                    scheduled_mw=mw,
                    status="DRAFT",
                )
            )

    await db.commit()
    return Fahrplan(
        schedule_id=schedule_id,
        portfolio_id=body.portfolio_id,
        date=body.date,
        created_at=now,
        intervals=intervals,
    )
