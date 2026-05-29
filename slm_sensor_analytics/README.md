# SLM Machine Sensor Analytics & Predictive Maintenance

A containerized Python FastAPI microservice that ingests high-frequency multi-sensor time-series readings (temperature, vibration, pressure, current, RPM), extracts rolling-window statistical features, trains unsupervised `scikit-learn` Isolation Forest anomaly detection models per device/sensor, and persists real-time predictive maintenance alerts in a PostgreSQL database.

## Tech Stack

| Layer | Technology |
|---|---|
| API | FastAPI + Pydantic v2 |
| ML Engine | scikit-learn (Isolation Forest) |
| Feature Extraction | numpy + scipy (mean, std, RMS, peak-to-peak, Fisher's kurtosis) |
| Database | PostgreSQL 16 + SQLAlchemy 2.0 (asyncpg) |
| Migrations | Alembic |
| Testing | pytest + pytest-asyncio + aiosqlite (26 tests) |
| Containerization | Docker Compose + multi-stage Dockerfile (uv-based) |

## Quickstart

### Run with Docker Compose

To spin up the service along with PostgreSQL database:

```bash
cd slm_sensor_analytics
docker compose build
docker compose up -d
```

- Swagger UI / OpenAPI docs: `http://localhost:8001/docs` (internal port `8000` mapped to local `8001`)
- Prometheus metrics: `http://localhost:8001/api/v1/metrics`

### Run Local Development & Tests

We leverage the monorepo's shared virtual environment at the root of `iot_dosing_controller`.

```bash
# From the root directory of the repository:
uv sync

# Run the 26-test suite using SQLite in-memory override:
PYTHONPATH=slm_sensor_analytics uv run pytest slm_sensor_analytics -v
```

## API Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | Liveness health check |
| `POST` | `/api/v1/ingest` | Ingest bulk sensor measurements |
| `POST` | `/api/v1/train` | Train an Isolation Forest model on historical readings |
| `POST` | `/api/v1/predict` | Run anomaly detection on recent readings and log alerts |
| `GET` | `/api/v1/alerts` | Retrieve sorted historical anomaly alerts (filterable by `device_id`) |
| `GET` | `/api/v1/metrics` | Expose Prometheus metrics |

## Statistical Feature Extraction

For each window of sensor values, we extract a 5-element feature vector:
1. **Mean**: Average signal value.
2. **Standard Deviation**: Signal spread.
3. **Root Mean Square (RMS)**: Total energy in the signal.
4. **Peak-to-Peak**: Range (`max - min`) to capture transient spikes.
5. **Kurtosis**: Calculated using Fisher's formulation (with bias-free sample correction when length $\ge 4$) to measure shape heaviness. If the variance is zero or length $< 4$, it defaults to `0.0`.

## Testing Summary

Our suite has **26 pytest tests** covering:
- **Health Endpoints**: Liveness and Prometheus metrics endpoints.
- **Ingestion & Validation**: Single/bulk payloads and Pydantic validation checks.
- **Mathematical Features**: Calculation correctness of RMS, peak-to-peak, Fisher sample kurtosis, and zero-variance limits.
- **Model Store Operations**: Fitting, joblib serialization, local disk caching, and missing-model exceptions.
- **Training Endpoint**: Batch training flow on database readings.
- **Prediction & Anomalies**: Outlier classification (verifying that severe outliers like `999.0` successfully trigger alerts and database entries) and custom lookback windows.
- **Alert Persistence**: Sorted alerts listing and database filter validations.
