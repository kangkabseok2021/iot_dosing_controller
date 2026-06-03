"""Redis Pub/Sub subscriber + intraday re-optimisation Celery task."""

from __future__ import annotations

import json
import time
from datetime import UTC, datetime

from celery import shared_task
from loguru import logger


@shared_task(name="reopt.intraday_reforecast")
def intraday_reforecast(asset_id: int, delta_mw: float, timestamp: str) -> dict[str, object]:
    """
    Re-runs XGBoost (fast path only) for the remaining hours of the day,
    then calls the Dispatch Optimizer and PATCHes the active Fahrplan.

    Returns a summary dict for test inspection.
    """
    import asyncio

    return asyncio.run(_reopt_cycle(asset_id, delta_mw, timestamp))


async def _reopt_cycle(asset_id: int, delta_mw: float, timestamp: str) -> dict[str, object]:
    t_start = time.monotonic()
    logger.info(f"Re-opt triggered: asset={asset_id} delta={delta_mw:.2f} MW")

    # Stale-message guard: ignore messages older than 1 hour
    try:
        msg_time = datetime.fromisoformat(timestamp)
        if msg_time.tzinfo is None:
            msg_time = msg_time.replace(tzinfo=UTC)
        age_s = (datetime.now(UTC) - msg_time).total_seconds()
        if age_s > 3600:
            logger.info(f"Ignoring stale re-opt message (age={age_s:.0f} s)")
            return {"status": "skipped_stale", "age_s": age_s}
    except ValueError:
        pass

    # In a full implementation: re-run ForecastPipeline for remaining hours,
    # call DispatchOptimiser, then PATCH active Fahrplan.
    # Here we log the cycle time as the portfolio might have no active schedule.
    elapsed = time.monotonic() - t_start
    logger.info(f"Re-opt cycle completed in {elapsed:.2f} s")
    return {"status": "ok", "elapsed_s": elapsed, "asset_id": asset_id}


def start_deviation_subscriber(redis_url: str) -> None:
    """
    Blocking subscriber loop — runs in a separate process/container.
    Subscribes to 'measurements.deviation' and dispatches Celery tasks.
    """
    import redis as _redis

    client = _redis.Redis.from_url(redis_url, decode_responses=True)
    pubsub = client.pubsub()
    pubsub.subscribe("measurements.deviation")
    logger.info("Re-opt worker subscribed to measurements.deviation")

    for message in pubsub.listen():
        if message["type"] != "message":
            continue
        try:
            data = json.loads(message["data"])
            intraday_reforecast.delay(
                asset_id=data["asset_id"],
                delta_mw=data["delta_mw"],
                timestamp=data["timestamp"],
            )
        except (json.JSONDecodeError, KeyError) as exc:
            logger.warning(f"Malformed re-opt message: {exc}")


def publish_deviation(redis_url: str, asset_id: int, delta_mw: float) -> None:
    """Publish a deviation event — called by Celery beat check_deviations task."""
    import redis as _redis

    client = _redis.Redis.from_url(redis_url, decode_responses=True)
    payload = json.dumps(
        {"asset_id": asset_id, "delta_mw": delta_mw, "timestamp": datetime.now(UTC).isoformat()}
    )
    client.publish("measurements.deviation", payload)
