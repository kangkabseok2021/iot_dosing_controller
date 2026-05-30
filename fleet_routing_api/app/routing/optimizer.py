from dataclasses import dataclass

from app.routing.haversine import haversine


@dataclass
class RouteWaypoint:
    id: int
    lat: float
    lon: float


def nearest_neighbor_route(
    depot: RouteWaypoint, waypoints: list[RouteWaypoint]
) -> list[RouteWaypoint]:
    """Greedy O(n²) nearest-neighbour heuristic; ~20-25% above optimal (Rosenkrantz 1977)."""
    if not waypoints:
        return []
    remaining = list(waypoints)
    current = depot
    ordered: list[RouteWaypoint] = []
    while remaining:
        distances = [haversine(current.lat, current.lon, w.lat, w.lon) for w in remaining]
        idx = distances.index(min(distances))
        current = remaining.pop(idx)
        ordered.append(current)
    return ordered


def total_route_distance(depot: RouteWaypoint, ordered: list[RouteWaypoint]) -> float:
    """Sum Haversine legs depot→w₁→…→wₙ, rounded to 3 dp."""
    if not ordered:
        return 0.0
    stops = [depot] + ordered
    total = sum(
        haversine(stops[i].lat, stops[i].lon, stops[i + 1].lat, stops[i + 1].lon)
        for i in range(len(stops) - 1)
    )
    return round(total, 3)
