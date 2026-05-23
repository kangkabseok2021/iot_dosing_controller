# Containerized Grid Load Forecasting API

A scalable Python backend that ingests time-series energy consumption data from simulated smart-meter
nodes, stores it in a normalized PostgreSQL schema optimized for time-series queries, runs an
asynchronous SMA forecasting worker, and serves load history and short-horizon forecasts via a
versioned FastAPI REST API.

## Stack

| Layer | Technology |
|---|---|
| API | FastAPI + Pydantic v2 |
| ORM | SQLAlchemy 2.0 async + asyncpg |
| Migrations | Alembic |
| Worker | asyncio.Task (60 s cycle) |
| Forecasting | SMA — O(n) sliding-sum |
| Monitoring | Prometheus metrics |
| Infra | Docker Compose (api + postgres + worker + prometheus) |
| CI | GitHub Actions — 4 jobs |

## Quickstart

```bash
# Start postgres + API (hot-reload)
make dev

# Seed 10 nodes × 90 days of synthetic load data
make seed

# Get a forecast
curl http://localhost:8000/api/v1/forecast/NODE-001

# OpenAPI docs
open http://localhost:8000/docs
```

## API Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/v1/health` | DB liveness check |
| `POST` | `/api/v1/readings` | Ingest one validated reading |
| `POST` | `/api/v1/readings/batch` | Ingest up to 1 000 readings |
| `GET` | `/api/v1/readings/{node_id}` | Paginated history |
| `GET` | `/api/v1/nodes` | All nodes with summary stats |
| `GET` | `/api/v1/forecast/{node_id}` | SMA forecast + anomaly flags |
| `GET` | `/api/v1/metrics` | Prometheus metrics |

## Validation Rules

- `node_id`: pattern `^[A-Z0-9_-]+$`, length 3–32
- `timestamp`: must not be > 60 s in the future
- `kwh`: `> 0`, `≤ 10 000`; additionally capped per `meter_type`:
  - `residential` ≤ 50 kWh, `commercial` ≤ 500 kWh, `industrial` ≤ 10 000 kWh

## SMA Forecaster

```
SMA_k[i] = (1/k) × Σ p_{i-k+1 .. i}    for i ≥ k-1
SMA_k[i] = None                           for i < k-1
```

- O(n) sliding-sum — no pandas (see [ADR-001](docs/ADR-001-no-pandas.md))
- Anomaly flag: `|reading − SMA| > 2σ`
- Worker cycle: every 60 s, iterates all nodes, UPSERTs `node_forecasts`
- Horizon projection: repeats last SMA value (see [ADR-002](docs/ADR-002-naive-extrapolation.md))

## Testing

```bash
make test          # unit + math (no Docker)
make test-math     # SMA correctness only
pytest tests/test_integration.py -m integration  # needs docker compose up
```

## CI Jobs

| Job | What it checks |
|---|---|
| `lint` | ruff + black |
| `unit-tests` | API + SMA tests, SQLite in-memory, no Docker |
| `math-accuracy` | SMA correctness in isolation — proves O(n) is correct at k=3,5,12,24,96 |
| `integration-tests` | Full docker compose stack — ingest → forecast round-trip |

## Docs

- [DB Schema](docs/DB-SCHEMA.md)
- [Query Plan Analysis](docs/QUERY-PLAN.md)
- [ADR-001: No pandas](docs/ADR-001-no-pandas.md)
- [ADR-002: Naive extrapolation](docs/ADR-002-naive-extrapolation.md)
