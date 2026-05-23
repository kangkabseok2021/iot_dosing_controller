"""Unit tests for FastAPI endpoints — uses in-memory SQLite, no PostgreSQL."""

from datetime import datetime, timedelta, timezone

import pytest


def _ts(delta_s: float = 0) -> str:
    return (datetime.now(tz=timezone.utc) + timedelta(seconds=delta_s)).isoformat()


@pytest.mark.asyncio
async def test_valid_reading_returns_201(client):
    resp = await client.post(
        "/api/v1/readings",
        json={"node_id": "NODE-001", "timestamp": _ts(-10), "kwh": 12.5},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["node_id"] == "NODE-001"
    assert isinstance(body["id"], int)


@pytest.mark.asyncio
async def test_future_timestamp_rejected(client):
    resp = await client.post(
        "/api/v1/readings",
        json={"node_id": "NODE-001", "timestamp": _ts(300), "kwh": 5.0},
    )
    assert resp.status_code == 422
    detail = resp.json()["detail"]
    assert any("timestamp" in str(d["loc"]) for d in detail)


@pytest.mark.asyncio
async def test_negative_kwh_rejected(client):
    resp = await client.post(
        "/api/v1/readings",
        json={"node_id": "NODE-001", "timestamp": _ts(-10), "kwh": -0.1},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_batch_over_limit_rejected(client):
    readings = [
        {"node_id": "NODE-001", "timestamp": _ts(-i), "kwh": 1.0} for i in range(1001)
    ]
    resp = await client.post("/api/v1/readings/batch", json={"readings": readings})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_invalid_node_id_format_rejected(client):
    resp = await client.post(
        "/api/v1/readings",
        json={"node_id": "abc def", "timestamp": _ts(-10), "kwh": 5.0},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_residential_kwh_over_cap_rejected(client):
    resp = await client.post(
        "/api/v1/readings",
        json={"node_id": "NODE-001", "timestamp": _ts(-10), "kwh": 100.0, "meter_type": "residential"},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_health_endpoint_db_up(client):
    resp = await client.get("/api/v1/health")
    assert resp.status_code == 200
    assert resp.json()["db"] == "ok"
