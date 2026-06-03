"""Phase 1 — 6 tests: assets + telemetry ingestion + TimescaleDB + Celery deviation."""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime, timedelta

import pytest

# ── helpers ──────────────────────────────────────────────────────────────────


async def _make_asset(client, **kwargs) -> dict:
    payload = {"name": "Wind-01", "type": "wind", "capacity_mw": 100.0} | kwargs
    resp = await client.post("/api/assets", json=payload)
    assert resp.status_code == 201
    return resp.json()


# ── tests ─────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_asset_valid(client):
    data = await _make_asset(client, name="Solar-Alpha", type="solar", capacity_mw=50.0)
    assert data["id"] > 0
    assert data["capacity_mw"] == 50.0


@pytest.mark.asyncio
async def test_create_asset_invalid_capacity(client):
    resp = await client.post(
        "/api/assets",
        json={"name": "Bad", "type": "wind", "capacity_mw": -5.0},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_ingest_telemetry_bulk(client):
    asset = await _make_asset(client, name="Wind-Bulk", capacity_mw=80.0)
    now = datetime.now(UTC)
    rows = [
        {
            "asset_id": asset["id"],
            "measured_at": (now + timedelta(minutes=15 * i)).isoformat(),
            "power_mw": float(i * 5),
        }
        for i in range(10)
    ]
    resp = await client.post("/api/telemetry", json={"rows": rows})
    assert resp.status_code == 200
    assert resp.json()["inserted"] == 10


@pytest.mark.asyncio
async def test_ingest_rejects_over_capacity(client):
    asset = await _make_asset(client, name="Wind-OverCap", capacity_mw=30.0)
    now = datetime.now(UTC)
    rows = [{"asset_id": asset["id"], "measured_at": now.isoformat(), "power_mw": 999.0}]
    resp = await client.post("/api/telemetry", json={"rows": rows})
    assert resp.status_code == 422


@pytest.mark.asyncio
@pytest.mark.skipif(os.getenv("USE_TIMESCALEDB") != "1", reason="Requires TimescaleDB")
async def test_hypertable_partitioning_query(pg_client):
    """Asserts chunk_count > 0 after inserting 8+ days of data (TimescaleDB only)."""
    asset = await _make_asset(pg_client, name="TS-Asset", capacity_mw=100.0)
    base = datetime(2024, 1, 1, tzinfo=UTC)
    rows = [
        {
            "asset_id": asset["id"],
            "measured_at": (base + timedelta(hours=h)).isoformat(),
            "power_mw": float(h % 24 * 2),
        }
        for h in range(8 * 24)  # 8 days × 1-hour intervals
    ]
    await pg_client.post("/api/telemetry", json={"rows": rows})
    resp = await pg_client.get("/api/telemetry/chunks")
    assert resp.status_code == 200
    assert resp.json()["chunk_count"] > 0


@pytest.mark.asyncio
async def test_celery_deviation_publishes_redis():
    """Verifies publish_deviation writes to fakeredis channel."""
    import fakeredis

    from app.reopt.worker import publish_deviation

    server = fakeredis.FakeServer()
    fake = fakeredis.FakeRedis(server=server, decode_responses=True)

    # Subscribe first so the message is captured
    pubsub = fake.pubsub()
    pubsub.subscribe("measurements.deviation")
    pubsub.get_message()  # consume subscribe confirmation

    # Monkey-patch Redis.from_url for this call
    import unittest.mock as mock

    with mock.patch("redis.Redis.from_url", return_value=fake):
        publish_deviation("redis://fake", asset_id=1, delta_mw=-3.5)

    msg = pubsub.get_message(timeout=0.1)
    assert msg is not None
    data = json.loads(msg["data"])
    assert data["asset_id"] == 1
    assert data["delta_mw"] == pytest.approx(-3.5)
