"""5 tests for FastAPI endpoints."""

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from httpx import AsyncClient


def _event_payload(**overrides) -> dict:
    return {
        "plant_id": "PLT-001",
        "sensor_id": "TEMP-A",
        "timestamp": "2026-01-15T08:00:00Z",
        "value": 85.3,
        "unit": "°C",
    } | overrides


async def test_post_event_returns_201(client: AsyncClient):
    resp = await client.post("/api/v1/events", json=_event_payload())
    assert resp.status_code == 201
    body = resp.json()
    assert body["plant_id"] == "PLT-001"
    assert body["unit"] == "°C"
    assert "id" in body


async def test_post_event_invalid_unit_returns_422(client: AsyncClient):
    resp = await client.post("/api/v1/events", json=_event_payload(unit="psi"))
    assert resp.status_code == 422


async def test_get_events_returns_list(client: AsyncClient):
    await client.post("/api/v1/events", json=_event_payload())
    await client.post("/api/v1/events", json=_event_payload(plant_id="PLT-002"))
    resp = await client.get("/api/v1/events")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 2
    assert len(body["items"]) == 2


async def test_get_event_by_id(client: AsyncClient):
    post = await client.post("/api/v1/events", json=_event_payload())
    event_id = post.json()["id"]
    resp = await client.get(f"/api/v1/events/{event_id}")
    assert resp.status_code == 200
    assert resp.json()["id"] == event_id


async def test_get_event_not_found_returns_404(client: AsyncClient):
    resp = await client.get(f"/api/v1/events/{uuid4()}")
    assert resp.status_code == 404
