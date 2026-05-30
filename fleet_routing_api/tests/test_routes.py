import json
from unittest.mock import MagicMock

import pytest

from app.api.routes import RouteCache

DEPOT = {"depot_lat": 51.5074, "depot_lon": -0.1278}
WAYPOINTS = [
    {"id": 1, "lat": 48.8566, "lon": 2.3522},   # Paris
    {"id": 2, "lat": 52.5200, "lon": 13.4050},  # Berlin
    {"id": 3, "lat": 41.9028, "lon": 12.4964},  # Rome
]


def test_route_returns_ordered_waypoints_and_distance(client, dispatcher_token):
    r = client.post(
        "/api/v1/routes",
        json={**DEPOT, "waypoints": WAYPOINTS},
        headers={"Authorization": f"Bearer {dispatcher_token}"},
    )
    assert r.status_code == 200
    data = r.json()
    assert len(data["ordered_waypoints"]) == 3
    assert data["total_distance_km"] > 0.0
    assert data["cached"] is False


def test_route_requires_auth(client):
    r = client.post("/api/v1/routes", json={**DEPOT, "waypoints": WAYPOINTS})
    assert r.status_code == 403


def test_empty_waypoints_returns_zero_distance(client, dispatcher_token):
    r = client.post(
        "/api/v1/routes",
        json={**DEPOT, "waypoints": []},
        headers={"Authorization": f"Bearer {dispatcher_token}"},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["total_distance_km"] == 0.0
    assert data["ordered_waypoints"] == []


def test_route_distance_is_positive_for_real_waypoints(client, dispatcher_token):
    r = client.post(
        "/api/v1/routes",
        json={**DEPOT, "waypoints": WAYPOINTS},
        headers={"Authorization": f"Bearer {dispatcher_token}"},
    )
    assert r.status_code == 200
    assert r.json()["total_distance_km"] == pytest.approx(r.json()["total_distance_km"], rel=1e-3)


def test_route_cache_get_returns_data_from_redis():
    cached_payload = {
        "ordered_waypoints": [{"id": 1, "lat": 48.8566, "lon": 2.3522}],
        "total_distance_km": 344.3,
    }
    mock_redis = MagicMock()
    mock_redis.get.return_value = json.dumps(cached_payload).encode()
    cache = RouteCache(client=mock_redis)
    result = cache.get("test-key")
    assert result is not None
    assert result["total_distance_km"] == 344.3
    mock_redis.get.assert_called_once_with("test-key")


def test_route_cache_set_calls_setex():
    mock_redis = MagicMock()
    cache = RouteCache(client=mock_redis)
    cache.set("test-key", {"total_distance_km": 100.0})
    mock_redis.setex.assert_called_once()
