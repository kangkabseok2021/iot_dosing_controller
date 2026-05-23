"""
SMA_k = (1/k) * sum(readings[i-k+1 : i+1]) for i >= k-1, None otherwise.
O(n) sliding-sum: accumulate first window, then slide by adding new / dropping old.
"""

import asyncio
import statistics
from datetime import datetime, timezone
from typing import Optional

from loguru import logger
from prometheus_client import Counter, Gauge, Histogram

READINGS_INGESTED = Counter(
    "grid_readings_ingested_total", "Total readings ingested", ["node_id"]
)
FORECAST_KWH = Gauge("grid_forecast_kwh", "Latest forecast kWh", ["node_id"])
ANOMALIES_TOTAL = Counter("grid_anomalies_total", "Total anomalies detected", ["node_id"])
CYCLE_DURATION = Histogram(
    "grid_worker_cycle_duration_seconds", "ForecastWorker cycle duration in seconds"
)


def compute_sma(readings: list[float], k: int) -> list[Optional[float]]:
    """Compute Simple Moving Average with O(n) sliding-sum."""
    n = len(readings)
    result: list[Optional[float]] = [None] * n
    if k <= 0 or k > n:
        return result
    window_sum = sum(readings[:k])
    result[k - 1] = window_sum / k
    for i in range(k, n):
        window_sum += readings[i] - readings[i - k]
        result[i] = window_sum / k
    return result


def compute_anomalies(
    readings: list[float], sma: list[Optional[float]]
) -> list[dict]:
    """Flag readings where |reading - sma| > 2 * stdev(readings)."""
    if len(readings) < 2:
        return []
    try:
        std = statistics.stdev(readings)
    except statistics.StatisticsError:
        return []
    flags = []
    for i, (r, s) in enumerate(zip(readings, sma)):
        if s is None:
            continue
        diff = abs(r - s)
        if std > 0 and diff > 2 * std:
            flags.append({"index": i, "kwh": r, "zscore": round(diff / std, 3)})
    return flags


class ForecastWorker:
    def __init__(self, interval_s: float = 60.0):
        self._interval = interval_s
        self._task: asyncio.Task | None = None
        self._stop_event = asyncio.Event()

    async def start(self) -> None:
        self._stop_event.clear()
        self._task = asyncio.create_task(self._run(), name="forecast-worker")
        logger.info("ForecastWorker started (interval={}s)", self._interval)

    async def stop(self) -> None:
        self._stop_event.set()
        if self._task:
            try:
                await asyncio.wait_for(self._task, timeout=self._interval + 5)
            except (asyncio.TimeoutError, asyncio.CancelledError):
                self._task.cancel()
        logger.info("ForecastWorker stopped")

    async def _run(self) -> None:
        from app.config import settings
        from app.db.session import AsyncSessionLocal
        from app.services.reading_service import ReadingService

        k = settings.SMA_WINDOW_SIZE
        while not self._stop_event.is_set():
            t_start = asyncio.get_event_loop().time()
            try:
                async with AsyncSessionLocal() as session:
                    svc = ReadingService(session)
                    summaries = await svc.get_node_summaries()
                    nodes_processed = 0
                    anomalies_found = 0
                    for summary in summaries:
                        if self._stop_event.is_set():
                            break
                        rows = await svc.get_recent(summary.node_id, limit=k * 4)
                        if not rows:
                            continue
                        kwh_series = [r.kwh for r in reversed(rows)]
                        sma = compute_sma(kwh_series, k)
                        last_sma = next((v for v in reversed(sma) if v is not None), None)
                        if last_sma is not None:
                            await svc.upsert_forecast(summary.node_id, last_sma, k)
                            FORECAST_KWH.labels(node_id=summary.node_id).set(last_sma)
                        anomalies = compute_anomalies(kwh_series, sma)
                        if anomalies:
                            ANOMALIES_TOTAL.labels(node_id=summary.node_id).inc(len(anomalies))
                            anomalies_found += len(anomalies)
                        nodes_processed += 1
                    await session.commit()
                elapsed_ms = (asyncio.get_event_loop().time() - t_start) * 1000
                CYCLE_DURATION.observe(elapsed_ms / 1000)
                logger.info(
                    "ForecastWorker cycle: nodes={} duration_ms={:.1f} anomalies={}",
                    nodes_processed,
                    elapsed_ms,
                    anomalies_found,
                )
            except Exception:
                logger.exception("ForecastWorker cycle error — retrying in 5s")
                await asyncio.sleep(5)
                continue

            try:
                await asyncio.wait_for(
                    asyncio.shield(asyncio.ensure_future(self._stop_event.wait())),
                    timeout=self._interval,
                )
            except asyncio.TimeoutError:
                pass
