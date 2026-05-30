import hashlib
import json
from dataclasses import dataclass
from typing import Optional

import redis as redis_lib
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.auth.dependencies import require_dispatcher
from app.config import settings
from app.routing.optimizer import RouteWaypoint, nearest_neighbor_route, total_route_distance

router = APIRouter(prefix="/api/v1/routes", tags=["routes"])


@dataclass
class RouteCache:
    client: Optional[redis_lib.Redis]
    TTL: int = 300

    def _make_key(self, depot_lat: float, depot_lon: float, waypoints: list) -> str:
        sorted_wps = sorted([(w.lat, w.lon) for w in waypoints])
        data = json.dumps({"depot": [depot_lat, depot_lon], "wps": sorted_wps})
        return "route:" + hashlib.sha256(data.encode()).hexdigest()

    def get(self, key: str) -> Optional[dict]:
        if not self.client:
            return None
        val = self.client.get(key)
        return json.loads(val) if val else None

    def set(self, key: str, data: dict) -> None:
        if not self.client:
            return
        self.client.setex(key, self.TTL, json.dumps(data))


def get_cache() -> RouteCache:
    try:
        client = redis_lib.from_url(settings.redis_url, socket_connect_timeout=1)
        client.ping()
        return RouteCache(client=client)
    except Exception:
        return RouteCache(client=None)


class WaypointInput(BaseModel):
    id: int
    lat: float
    lon: float


class RouteRequest(BaseModel):
    depot_lat: float
    depot_lon: float
    waypoints: list[WaypointInput]


class RouteResponse(BaseModel):
    ordered_waypoints: list[WaypointInput]
    total_distance_km: float
    cached: bool


@router.post("", response_model=RouteResponse, dependencies=[Depends(require_dispatcher)])
def optimise_route(
    body: RouteRequest, cache: RouteCache = Depends(get_cache)
) -> RouteResponse:
    depot = RouteWaypoint(id=0, lat=body.depot_lat, lon=body.depot_lon)
    wps = [RouteWaypoint(id=w.id, lat=w.lat, lon=w.lon) for w in body.waypoints]

    cache_key = cache._make_key(body.depot_lat, body.depot_lon, wps)
    cached_val = cache.get(cache_key)
    if cached_val:
        return RouteResponse(**cached_val, cached=True)

    ordered = nearest_neighbor_route(depot, wps)
    distance = total_route_distance(depot, ordered)

    result = RouteResponse(
        ordered_waypoints=[WaypointInput(id=w.id, lat=w.lat, lon=w.lon) for w in ordered],
        total_distance_km=distance,
        cached=False,
    )
    cache.set(cache_key, result.model_dump(exclude={"cached"}))
    return result
