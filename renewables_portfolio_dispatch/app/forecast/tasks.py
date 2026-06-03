"""Celery tasks for async forecast computation."""

from __future__ import annotations

import json
from datetime import UTC, datetime

import pandas as pd
from celery import shared_task
from loguru import logger
from sqlalchemy import select

from app.forecast.pipeline import ForecastPipeline
from app.models.orm import ForecastInterval, ForecastRun, Telemetry


@shared_task(name="forecast.run_forecast", bind=True)
def run_forecast(self: object, asset_id: int, horizon_h: int = 24) -> dict:  # type: ignore[type-arg]
    """Synchronous wrapper executed by Celery worker."""
    import asyncio

    return asyncio.run(_run_forecast_async(asset_id, horizon_h))


async def _run_forecast_async(asset_id: int, horizon_h: int) -> dict:
    from app.database import SessionLocal

    async with SessionLocal() as db:
        # Fetch 90-day rolling window (at most 90*24*4 = 8640 rows)
        result = await db.execute(
            select(Telemetry)
            .where(Telemetry.asset_id == asset_id)
            .order_by(Telemetry.measured_at.desc())
            .limit(8640)
        )
        rows = result.scalars().all()

    if len(rows) < 40:
        logger.warning(f"Asset {asset_id}: not enough data ({len(rows)} rows)")
        return {"status": "insufficient_data"}

    series = pd.Series(
        [r.power_mw for r in reversed(rows)],
        index=pd.DatetimeIndex([r.measured_at for r in reversed(rows)]),
        name="power_mw",
    )

    # Use simpler model for small datasets (avoids SARIMA convergence issues)
    if len(series) < 500:
        pipeline = ForecastPipeline(sarima_order=(1, 0, 1), seasonal_order=None)
    else:
        pipeline = ForecastPipeline()

    pipeline.fit(series)
    horizon_steps = horizon_h * 4  # 15-min intervals
    mu, sigma = pipeline.predict(horizon_steps)

    now = datetime.now(UTC)
    async with SessionLocal() as db:
        run = ForecastRun(
            asset_id=asset_id,
            created_at=now,
            horizon_h=horizon_h,
            mape=pipeline.mape_ensemble,
            model_params_json=json.dumps({"sarima": str(pipeline._sarima_order)}),
        )
        db.add(run)
        await db.flush()
        for i in range(horizon_steps):
            db.add(
                ForecastInterval(
                    run_id=run.id,
                    interval_start=now,
                    interval_end=now,
                    mean_mw=float(mu[i]),
                    std_mw=float(sigma[i]),
                )
            )
        await db.commit()
        await db.refresh(run)
        return {"run_id": run.id, "mape": run.mape}
