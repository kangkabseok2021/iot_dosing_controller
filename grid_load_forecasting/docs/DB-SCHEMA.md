# Database Schema

## Entity-Relationship Overview

```
nodes (node_id PK)
  └──< load_readings (id PK, node_id FK, ts, kwh, meter_type, accepted_at)
  └── node_forecasts (node_id PK FK, forecast_kwh, computed_at, window_size)
```

## Tables

### `nodes`
| Column | Type | Notes |
|---|---|---|
| node_id | VARCHAR(32) PK | e.g. `NODE-001`, pattern `^[A-Z0-9_-]+$` |
| region | VARCHAR(64) | optional |
| meter_type | VARCHAR(16) | `residential` / `commercial` / `industrial` |
| commissioned_at | TIMESTAMPTZ | optional |

### `load_readings`
| Column | Type | Notes |
|---|---|---|
| id | BIGSERIAL PK | auto-increment |
| node_id | VARCHAR(32) FK | → nodes ON DELETE CASCADE |
| ts | TIMESTAMPTZ NOT NULL | reading timestamp |
| kwh | FLOAT NOT NULL CHECK > 0 | kWh per interval |
| meter_type | VARCHAR(16) | denormalised for query convenience |
| accepted_at | TIMESTAMPTZ | server-side NOW() |

**Indexes:**
- `idx_readings_node_ts` on `(node_id, ts DESC)` — primary access pattern: latest N readings per node
- `idx_readings_ts` on `(ts DESC)` — fleet-wide time range scans

### `node_forecasts`
| Column | Type | Notes |
|---|---|---|
| node_id | VARCHAR(32) PK FK | → nodes ON DELETE CASCADE |
| forecast_kwh | FLOAT | latest SMA forecast |
| computed_at | TIMESTAMPTZ | last worker cycle time |
| window_size | INTEGER | SMA k used |
