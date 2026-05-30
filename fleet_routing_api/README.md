# Secure Logistics Fleet Routing API

FastAPI backend for a logistics operator — JWT-authenticated route optimisation via Haversine nearest-neighbour VRP, Redis route caching, and a normalised PostgreSQL fleet schema.

## Key features

| Feature | Detail |
|---------|--------|
| **Haversine distance** | `d = 2R·arcsin(√(sin²(Δφ/2) + cosφ₁·cosφ₂·sin²(Δλ/2)))` — O(1) per pair |
| **Nearest-neighbour VRP** | Greedy O(n²) heuristic — ~20-25% above optimal (Rosenkrantz 1977) |
| **JWT RBAC** | HS256 tokens; `dispatcher` role required for all write/route endpoints |
| **Redis route cache** | SHA-256 keyed by sorted waypoints — 300 s TTL, degrades gracefully |
| **PostgreSQL schema** | Vehicle ← Driver, Vehicle ← Delivery ← Waypoint (FK constraints) |
| **24 pytest tests** | 4 Haversine + 5 optimizer + 5 auth + 4 delivery + 6 route — 94.5% coverage |

## Quick start

```bash
docker compose up -d
```

API available at `http://localhost:8000`. Docs at `http://localhost:8000/docs`.

## Auth

```bash
curl -X POST http://localhost:8000/api/v1/auth/token \
  -H 'Content-Type: application/json' \
  -d '{"username": "dispatcher1", "password": "dispatch123"}'
```

Use the returned `access_token` as `Authorization: Bearer <token>` on all other requests.

## Route optimisation

```bash
curl -X POST http://localhost:8000/api/v1/routes \
  -H 'Authorization: Bearer <token>' \
  -H 'Content-Type: application/json' \
  -d '{
    "depot_lat": 51.5074, "depot_lon": -0.1278,
    "waypoints": [
      {"id": 1, "lat": 48.8566, "lon": 2.3522},
      {"id": 2, "lat": 52.5200, "lon": 13.4050},
      {"id": 3, "lat": 41.9028, "lon": 12.4964}
    ]
  }'
```

## Development

```bash
uv sync
uv run pytest tests/ -v
uv run flake8 app/ tests/
```

## Math

See [docs/ROUTING-MATH.md](docs/ROUTING-MATH.md) for formula derivation, complexity analysis, and optimality gap discussion.
