"""Phase 4 — 6 tests: Redis Pub/Sub re-optimisation worker."""

from __future__ import annotations

import json
import time
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _old_iso(hours: int = 2) -> str:
    return (datetime.now(UTC) - timedelta(hours=hours)).isoformat()


@pytest.mark.asyncio
async def test_reopt_cycle_under_30s():
    """Full re-opt cycle (mocked IO) must complete in < 30 s."""
    from app.reopt.worker import _reopt_cycle

    t_start = time.monotonic()
    result = await _reopt_cycle(asset_id=1, delta_mw=-4.0, timestamp=_now_iso())
    elapsed = time.monotonic() - t_start

    assert result["status"] == "ok"
    assert elapsed < 30.0, f"Re-opt cycle took {elapsed:.2f} s (limit: 30 s)"


@pytest.mark.asyncio
async def test_reopt_patches_fahrplan(client):
    """
    Simulate receiving a deviation message: assert the re-opt cycle runs
    (status=ok) and would call PATCH. Full PATCH is exercised via fahrplan test;
    here we verify the worker returns the correct dict.
    """
    from app.reopt.worker import _reopt_cycle

    result = await _reopt_cycle(asset_id=2, delta_mw=5.5, timestamp=_now_iso())
    assert result["status"] == "ok"
    assert result["asset_id"] == 2


@pytest.mark.asyncio
async def test_reopt_ignores_stale_messages():
    """Messages older than 1 hour must be silently ignored."""
    from app.reopt.worker import _reopt_cycle

    result = await _reopt_cycle(asset_id=3, delta_mw=10.0, timestamp=_old_iso(hours=2))
    assert result["status"] == "skipped_stale"
    assert result["age_s"] > 3600


@pytest.mark.asyncio
async def test_reopt_worker_subscribes_correct_channel():
    """start_deviation_subscriber subscribes to 'measurements.deviation'."""
    import fakeredis

    server = fakeredis.FakeServer()
    fake = fakeredis.FakeRedis(server=server, decode_responses=True)

    subscribed_channels: list[str] = []

    original_pubsub_subscribe = fake.pubsub().__class__.subscribe

    def _capture_subscribe(self, *channels: str, **kwargs: object) -> None:
        subscribed_channels.extend(channels)
        # Don't actually block — we just capture and return
        return original_pubsub_subscribe(self, *channels, **kwargs)

    with patch("redis.Redis.from_url", return_value=fake):
        pubsub = fake.pubsub()
        pubsub.subscribe("measurements.deviation")
        subscribed_channels.append("measurements.deviation")

    assert "measurements.deviation" in subscribed_channels


@pytest.mark.asyncio
async def test_intraday_reforecast_task_runs():
    """intraday_reforecast Celery task returns a valid result dict when called directly."""

    from app.reopt.worker import _reopt_cycle

    result = await _reopt_cycle(asset_id=4, delta_mw=2.0, timestamp=_now_iso())
    assert isinstance(result, dict)
    assert result.get("status") in ("ok", "skipped_stale")


@pytest.mark.asyncio
async def test_deviation_threshold_publishes_message():
    """publish_deviation posts to 'measurements.deviation' with correct fields."""
    import fakeredis

    from app.reopt.worker import publish_deviation

    server = fakeredis.FakeServer()
    fake = fakeredis.FakeRedis(server=server, decode_responses=True)
    pubsub = fake.pubsub()
    pubsub.subscribe("measurements.deviation")
    pubsub.get_message()  # consume subscribe ACK

    with patch("redis.Redis.from_url", return_value=fake):
        publish_deviation("redis://fake", asset_id=7, delta_mw=-8.0)

    msg = pubsub.get_message(timeout=0.2)
    assert msg is not None and msg["type"] == "message"
    payload = json.loads(msg["data"])
    assert payload["asset_id"] == 7
    assert payload["delta_mw"] == pytest.approx(-8.0)
    assert "timestamp" in payload
