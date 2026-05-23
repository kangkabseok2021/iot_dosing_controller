from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.models.reading import (
    AnomalyFlag,
    ForecastResponse,
    LoadReading,
    LoadReadingBatch,
    NodeSummary,
    ReadingResponse,
)
from app.services.reading_service import ReadingService
from app.workers.forecaster import compute_anomalies, compute_sma

router = APIRouter(prefix="/api/v1")


@router.get("/health")
async def health(session: AsyncSession = Depends(get_session)):
    try:
        await session.execute(text("SELECT 1"))
        return {"db": "ok"}
    except Exception:
        raise HTTPException(status_code=503, detail="db unavailable")


@router.post("/readings", response_model=ReadingResponse, status_code=201)
async def ingest_reading(
    reading: LoadReading,
    session: AsyncSession = Depends(get_session),
):
    svc = ReadingService(session)
    result = await svc.ingest(reading)
    await session.commit()
    return result


@router.post("/readings/batch", status_code=201)
async def ingest_batch(
    batch: LoadReadingBatch,
    session: AsyncSession = Depends(get_session),
):
    svc = ReadingService(session)
    import asyncio

    results = await asyncio.gather(*[svc.ingest(r) for r in batch.readings])
    await session.commit()
    return {"accepted": len(results)}


@router.get("/readings/{node_id}", response_model=list[ReadingResponse])
async def get_readings(
    node_id: str,
    limit: int = Query(96, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    from_ts: Optional[datetime] = None,
    to_ts: Optional[datetime] = None,
    session: AsyncSession = Depends(get_session),
):
    svc = ReadingService(session)
    rows = await svc.get_recent(node_id, limit=limit, offset=offset, from_ts=from_ts, to_ts=to_ts)
    return [
        ReadingResponse(id=r.id, node_id=r.node_id, timestamp=r.ts, kwh=r.kwh, accepted_at=r.accepted_at)
        for r in rows
    ]


@router.get("/nodes", response_model=list[NodeSummary])
async def list_nodes(session: AsyncSession = Depends(get_session)):
    svc = ReadingService(session)
    return await svc.get_node_summaries()


@router.get("/forecast/{node_id}", response_model=ForecastResponse)
async def get_forecast(
    node_id: str,
    horizon_steps: int = Query(4, ge=1, le=24),
    session: AsyncSession = Depends(get_session),
):
    from app.config import settings

    svc = ReadingService(session)
    k = settings.SMA_WINDOW_SIZE
    rows = await svc.get_recent(node_id, limit=k * 4)
    if not rows:
        raise HTTPException(status_code=404, detail=f"No readings for node {node_id!r}")

    rows_asc = list(reversed(rows))
    kwh_series = [r.kwh for r in rows_asc]
    sma_series = compute_sma(kwh_series, k)
    anomalies = compute_anomalies(kwh_series, sma_series)

    last_sma = next((v for v in reversed(sma_series) if v is not None), None)
    forecast_rec = await svc.get_forecast(node_id)
    forecast_kwh = forecast_rec.forecast_kwh if forecast_rec else last_sma
    computed_at = forecast_rec.computed_at if forecast_rec else None

    n = len(kwh_series)
    confidence: str
    if n >= k * 4:
        confidence = "high"
    elif n >= k:
        confidence = "medium"
    else:
        confidence = "low"

    last_ts = rows_asc[-1].ts
    from datetime import timedelta

    horizon = [
        {
            "step": i + 1,
            "ts": (last_ts + timedelta(minutes=15 * (i + 1))).isoformat(),
            "projected_kwh": forecast_kwh,
        }
        for i in range(horizon_steps)
    ]

    raw = [
        {"ts": r.ts.isoformat(), "kwh": r.kwh, "sma": sma_series[i]}
        for i, r in enumerate(rows_asc)
    ]

    anomaly_flags = [
        AnomalyFlag(ts=rows_asc[a["index"]].ts, kwh=a["kwh"], zscore=a["zscore"])
        for a in anomalies
    ]

    return ForecastResponse(
        node_id=node_id,
        forecast_kwh=forecast_kwh,
        computed_at=computed_at,
        window_size=k,
        confidence=confidence,
        raw_readings=raw,
        anomaly_flags=anomaly_flags,
        horizon=horizon,
    )
