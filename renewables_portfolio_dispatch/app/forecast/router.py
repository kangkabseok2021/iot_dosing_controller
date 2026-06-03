from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.orm import ForecastRun
from app.models.schemas import ForecastRunRead

router = APIRouter(prefix="/api/forecast", tags=["forecast"])


@router.post("/{asset_id}")
async def trigger_forecast(
    asset_id: int,
    background_tasks: BackgroundTasks,
    horizon_h: int = 24,
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    from app.forecast.tasks import _run_forecast_async

    # Run as background task (in tests Celery is eager or we call directly)
    background_tasks.add_task(_run_forecast_async, asset_id, horizon_h)
    return {"status": "accepted", "asset_id": asset_id, "horizon_h": horizon_h}


@router.get("/{asset_id}/latest", response_model=ForecastRunRead)
async def get_latest_forecast(
    asset_id: int, db: AsyncSession = Depends(get_db)
) -> ForecastRun:
    result = await db.execute(
        select(ForecastRun)
        .where(ForecastRun.asset_id == asset_id)
        .order_by(ForecastRun.created_at.desc())
        .limit(1)
    )
    run = result.scalar_one_or_none()
    if run is None:
        raise HTTPException(status_code=404, detail="No forecast run found for asset")
    return run
