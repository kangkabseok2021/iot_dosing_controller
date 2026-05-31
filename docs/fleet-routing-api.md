# Secure Logistics Fleet Routing API

FastAPI backend for a logistics operator — JWT-authenticated route optimisation via Haversine nearest-neighbour VRP, Redis route caching, and a normalised PostgreSQL fleet schema. 24 pytest tests at 94.5% coverage.

---

## Architecture

```
POST /api/v1/auth/token
       │  JWT HS256 (dispatcher role required for writes)
┌──────▼──────────────────────────────────────────────────────────┐
│  FastAPI  (app/main.py)                                          │
│  auth router · deliveries router · routes router                │
└──────┬──────────────────────────────────────────────────────────┘
       │ JWT decode + role check on every route request
┌──────▼──────────────────────────────────────────────────────────┐
│  RouteOptimizer  (app/routing/optimizer.py)                      │
│  nearest-neighbour VRP — O(n²), ~20-25% above optimal           │
│  haversine(φ₁,λ₁,φ₂,λ₂) = 2R·arcsin(√(sin²(Δφ/2)+…))         │
└──────┬──────────────────────────────────────────────────────────┘
       │ SHA-256 cache key (sorted waypoints)
┌──────▼──────────────────────────────────────────────────────────┐
│  Redis route cache  (TTL 300 s)                                  │
│  Degrades gracefully — cache miss falls through to optimizer     │
└──────┬──────────────────────────────────────────────────────────┘
       │ async SQLAlchemy 2.0
┌──────▼──────────────────────────────────────────────────────────┐
│  PostgreSQL schema                                               │
│  Vehicle ← Driver  (FK)                                         │
│  Vehicle ← Delivery ← Waypoint  (FK, CASCADE)                   │
└─────────────────────────────────────────────────────────────────┘
```

---

## Routing Mathematics

### Haversine great-circle distance

```
a = sin²(Δφ/2) + cos(φ₁) · cos(φ₂) · sin²(Δλ/2)
d = 2R · arcsin(√a)     R = 6 371 km
```

Numerically stable for small distances (unlike the spherical law of cosines). O(1) per pair.

| Known value | Expected |
|---|---|
| Same point | 0.000 km |
| Equatorial 1° longitude | 111.195 km ± 0.01 |
| London → Paris | 344.3 km ± 1 |

### Nearest-neighbour VRP heuristic

```
current ← depot
while remaining:
    next ← argmin haversine(current, w) for w in remaining
    ordered.append(remaining.pop(next))
    current ← next
```

**Complexity:** O(n²). **Optimality gap:** ~20–25% above optimal (Rosenkrantz et al., 1977). For n > 20 use OR-Tools or 2-opt post-processing.

---

## REST API

| Method | Path | Auth | Description |
|---|---|---|---|
| `POST` | `/api/v1/auth/token` | — | Issue JWT; body: `{username, password}` |
| `GET` | `/api/v1/deliveries` | dispatcher | List deliveries with waypoints |
| `POST` | `/api/v1/deliveries` | dispatcher | Create delivery + waypoints |
| `POST` | `/api/v1/routes` | dispatcher | Optimise route for a list of waypoints; Redis-cached 300 s |
| `GET` | `/health` | — | `{status: "ok"}` |

---

## Quick Start

```bash
# Full stack (FastAPI + PostgreSQL + Redis)
cd fleet_routing_api
docker compose up -d
# Docs: http://localhost:8000/docs

# Get a token
curl -X POST http://localhost:8000/api/v1/auth/token \
  -H 'Content-Type: application/json' \
  -d '{"username": "dispatcher1", "password": "dispatch123"}'

# Optimise a route
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

---

## Testing

```bash
cd fleet_routing_api
uv run pytest tests/ -v
```

**24 tests — SQLite in-memory, no Redis, no real JWT secrets. 94.5% coverage.**

| Suite | n | What it validates |
|---|---|---|
| `test_haversine` | 4 | Zero distance, equatorial 1°, London→Paris, antipodal |
| `test_optimizer` | 5 | Single waypoint, multi-stop order, depot-first, empty list |
| `test_auth` | 5 | Token issue, valid token decode, expired token, wrong role, missing header |
| `test_deliveries` | 4 | Create, list, FK cascade delete, Pydantic validation |
| `test_routes` | 6 | Optimised order returned, cache hit (same key), cache miss, degrades without Redis, large n order, 422 on empty waypoints |

See [fleet_routing_api/docs/ROUTING-MATH.md](../fleet_routing_api/docs/ROUTING-MATH.md) for full formula derivation and complexity analysis.
