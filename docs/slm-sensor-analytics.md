# SLM Machine Sensor Analytics & Predictive Maintenance

A containerised Python FastAPI microservice that ingests high-frequency multi-sensor time-series readings (temperature, vibration, pressure, current, RPM), extracts rolling-window statistical features, trains per-device Isolation Forest anomaly detection models, and persists real-time predictive maintenance alerts in PostgreSQL.

---

## Architecture

```
POST /api/v1/ingest  (device_id, sensor_type, values[], timestamp)
       │
┌──────▼──────────────────────────────────────────────────────────┐
│  FastAPI  (app/main.py)                                          │
│  Pydantic v2 — BulkIngestionRequest · MeasurementCreate         │
└──────┬──────────────────────────────────────────────────────────┘
       │ async SQLAlchemy 2.0 + asyncpg
┌──────▼──────────────────────────────────────────────────────────┐
│  SensorReadingRepository                                         │
│  bulk insert · list by device + sensor + time window            │
└──────┬──────────────────────────────────────────────────────────┘
       │
┌──────▼──────────────────────────────────────────────────────────┐
│  FeatureExtractor  (app/services/)                               │
│  window → [mean, std, RMS, peak-to-peak, kurtosis]              │
└──────┬──────────────────────────────────────────────────────────┘
       │
┌──────▼──────────────────────────────────────────────────────────┐
│  IsolationForestModel  (app/services/)                           │
│  fit(X) · predict(X) → anomaly score per window                 │
│  serialised via joblib, cached on local disk per device/sensor  │
└──────┬──────────────────────────────────────────────────────────┘
       │
┌──────▼──────────────────────────────────────────────────────────┐
│  AlertRepository                                                 │
│  persist anomaly alerts · list sorted by severity + time        │
└─────────────────────────────────────────────────────────────────┘
```

---

## Statistical Feature Extraction

For each rolling window of sensor values a 5-element feature vector is computed:

| Feature | Formula | Purpose |
|---|---|---|
| Mean | `μ = Σxᵢ / n` | Baseline offset |
| Std Dev | `σ = √(Σ(xᵢ−μ)² / (n−1))` | Signal spread |
| RMS | `√(Σxᵢ² / n)` | Signal energy — sensitive to bearing wear |
| Peak-to-Peak | `max(x) − min(x)` | Transient spike detection |
| Kurtosis | Fisher's formulation with Bessel correction (zero when σ=0 or n<4) | Distribution tail weight — catches impulsive faults |

---

## REST API

| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | Liveness check |
| `POST` | `/api/v1/ingest` | Bulk ingest sensor measurements |
| `POST` | `/api/v1/train` | Train Isolation Forest on historical readings for a device/sensor |
| `POST` | `/api/v1/predict` | Run anomaly detection + persist alerts |
| `GET` | `/api/v1/alerts` | Retrieve alerts, filterable by `device_id`, sorted by severity |
| `GET` | `/api/v1/metrics` | Prometheus exposition format |

---

## Quick Start

```bash
# Docker Compose (app + PostgreSQL)
cd slm_sensor_analytics
docker compose up -d
# Swagger UI: http://localhost:8001/docs
# Metrics:    http://localhost:8001/api/v1/metrics

# Ingest readings
curl -X POST http://localhost:8001/api/v1/ingest \
  -H "Content-Type: application/json" \
  -d '{"device_id":"CNC-01","sensor_type":"vibration","values":[0.1,0.2,0.15],"timestamp":"2026-01-15T08:00:00Z"}'

# Train model
curl -X POST "http://localhost:8001/api/v1/train?device_id=CNC-01&sensor_type=vibration"

# Predict
curl -X POST "http://localhost:8001/api/v1/predict?device_id=CNC-01&sensor_type=vibration"
```

---

## Testing

```bash
# From repo root
PYTHONPATH=slm_sensor_analytics uv run pytest slm_sensor_analytics -v
```

**26 tests — aiosqlite in-memory, no Docker, no PostgreSQL.**

| Suite | n | What it validates |
|---|---|---|
| Health & metrics | 2 | `/health` 200, `/api/v1/metrics` Prometheus format |
| Ingestion | 4 | Single + bulk payload, Pydantic validation, DB persistence |
| Feature math | 5 | RMS, peak-to-peak, Fisher kurtosis, zero-variance edge case |
| Model store | 4 | fit, joblib serialise/deserialise, disk cache, missing-model exception |
| Training | 3 | Batch training flow on DB readings |
| Prediction | 5 | Outlier classification (999.0 triggers alert), custom lookback |
| Alert persistence | 3 | Sorted listing, device_id filter, DB count |
