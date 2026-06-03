# IoT Dosing Controller, EV Battery HIL, SLM Sensor Analytics, Fleet Routing API, AWS Sensor API & Renewables Portfolio Dispatch

A collection of industrial IoT, predictive maintenance, logistics, energy trading, and cloud-native backend systems sharing edge daemon architectures, asyncio orchestration, and machine learning telemetry pipelines.

| Project | Description | Docs |
|---|---|---|
| **Edge IoT Dosing Controller** | C++17 Modbus TCP daemon + Python PLC simulator + FastAPI dashboard — deploys to Raspberry Pi 4 via Ansible | [Architecture ↓](#architecture) |
| **EV Battery HIL Test Simulator** | C++17 Thevenin ECM battery daemon + Python asyncio orchestrator with FastAPI, fault injection, and GitHub Actions ARM64 CI | [docs/ev-battery-hil.md](docs/ev-battery-hil.md) |
| **SLM Machine Sensor Analytics** | Multi-sensor telemetry ingestion, statistical feature extraction (RMS/Kurtosis), and Isolation Forest anomaly detection API | [docs/slm-sensor-analytics.md](docs/slm-sensor-analytics.md) |
| **Secure Logistics Fleet Routing API** | FastAPI + JWT RBAC + Haversine O(n²) VRP optimizer + Redis route cache (TTL 300 s) + SQLAlchemy fleet schema — 24 pytest tests at 94.5% coverage | [docs/fleet-routing-api.md](docs/fleet-routing-api.md) |
| **Cloud-Native Python Backend on AWS** | FastAPI + async SQLAlchemy 2.0 + S3 archival (boto3/asyncio.to_thread) + 4-module Terraform IaC (VPC · ECS Fargate · RDS PostgreSQL 16 · S3/IAM) — 15 pytest at 93% coverage via moto + aiosqlite | [docs/aws-sensor-api.md](docs/aws-sensor-api.md) |
| **Renewables Portfolio Dispatch Optimizer** | SARIMA + XGBoost ensemble day-ahead forecast · CVXPY/OSQP LP dispatcher · Fahrplan REST API (UUID, POST/GET/PATCH) · Redis Pub/Sub re-opt worker · Azure Blob archival + Bicep IaC · TimescaleDB hypertable · 25 pytest-asyncio | [Quick Start ↓](#renewables-portfolio-dispatch-optimizer) |

---

# Edge-based IoT Dosing Controller

A complete edge-IoT stack for pipeline and dosing technology: a **C++17 daemon** simulates RFID tags and flow sensors, exposes process registers over **Modbus TCP**, a **Python PLC simulator** polls and controls valve state, telemetry is persisted in **SQLite**, and a **FastAPI REST layer** drives a real-time dashboard. The whole system deploys on a Raspberry Pi 4 (or any ARM64 edge device) with a single Ansible command.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│  C++17 Dosing Daemon  (systemd, ARM64/x86_64)                   │
│                                                                   │
│   RfidSimulator ──┐                                               │
│   FlowSensor   ──┤──► DosingFsm ──► ModbusServer (port 5502)   │
│   (timerfd)       │    4-state FSM    Holding-Regs + Coils       │
└───────────────────┴─────────────────────────────────────────────┘
           Modbus TCP                      Modbus TCP
           (read regs)                    (write coils)
                ▲                               │
                │                               ▼
  ┌─────────────────────────┐    ┌──────────────────────────────┐
  │  Python Collector        │    │  Python PLC Simulator         │
  │  (poll every 500 ms)     │    │  (100 ms cycle)               │
  │  → SQLite WAL            │    │  decide_valve(regs) → coil   │
  └──────────┬──────────────┘    └──────────────────────────────┘
             │
        /data/dosing.db
             │
  ┌──────────▼──────────────┐
  │  FastAPI (port 8092)     │
  │  /api/metrics            │
  │  /api/events             │
  │  /api/status             │
  └──────────┬──────────────┘
             │  nginx (port 80)
  ┌──────────▼──────────────┐
  │  Vanilla JS Dashboard    │
  │  Chart.js auto-refresh   │
  └─────────────────────────┘
```

All Python services (collector, API, PLC simulator, dashboard) run as Docker Compose services. The C++ daemon runs as a `systemd` unit outside Docker so it retains direct access to `timerfd` and serial interfaces.

---

## Modbus Register Layout

| Address | Register        | Type         | Description                         |
|---------|-----------------|--------------|-------------------------------------|
| 40001   | flow_rate       | uint16       | Flow rate × 10 (fixed-point ml/min) |
| 40002   | valve_state     | uint16       | 0 = closed, 1 = open                |
| 40003   | total_volume_hi | uint16       | Accumulated volume (high word) ml   |
| 40004   | total_volume_lo | uint16       | Accumulated volume (low word) ml    |
| 40005–40012 | rfid_epc    | 8 × uint16   | Last RFID EPC (16 ASCII bytes)      |
| 40013   | dosing_state    | uint16       | 0=IDLE 1=DOSING 2=PAUSE 3=COMPLETE |

**Coils (written by PLC):**

| Address | Coil       | Description                |
|---------|------------|----------------------------|
| 0       | valve_cmd  | 1 = open valve             |
| 1       | reset_cmd  | 1 = reset FSM to IDLE      |

---

## Dosing FSM

```
      reset_cmd=1 (any state)
         ┌───────────────────────┐
         ▼                       │
       IDLE ──(rfid ∧ valve=1)──► DOSING ──(accumulated ≥ target)──► COMPLETE
                                    │  ▲
                              valve=0│  │valve=1
                                    ▼  │
                                  PAUSE
```

---

## Project Layout

```
iot_dosing_controller/
├── controller/              # C++17 Dosing daemon
│   ├── src/
│   │   ├── RfidSimulator.{h,cpp}   # EPC pool, Bernoulli trigger
│   │   ├── FlowSensor.{h,cpp}      # Q = k·f + Gaussian noise
│   │   ├── DosingFsm.{h,cpp}       # 4-state FSM
│   │   ├── ModbusServer.{h,cpp}    # libmodbus TCP server
│   │   └── main.cpp
│   ├── tests/
│   │   └── test_controller.cpp     # 13 GoogleTests
│   └── CMakeLists.txt
├── collector/               # Modbus → SQLite collector
├── api/                     # FastAPI REST layer
├── plc_simulator/           # Python PLC simulator
├── static/                  # Vanilla JS dashboard
├── tests/                   # Python tests (14 tests)
├── ansible/                 # Deployment playbook
├── docker-compose.yml
├── pyproject.toml
├── ev_battery_hil/          # ── EV Battery HIL Test Simulator ──────────
│   ├── bms/                 #   C++17 Thevenin ECM daemon (11 GoogleTests)
│   │   ├── src/
│   │   │   ├── BatteryModel.{h,cpp}       # Thevenin 1-RC ECM + RK4
│   │   │   ├── BmsStateMachine.{h,cpp}    # IDLE→DISCHARGING→CHARGING→FAULT
│   │   │   └── TelemetryServer.{h,cpp}    # TCP JSON 100 Hz
│   │   └── CMakeLists.txt
│   ├── orchestrator/        #   Python asyncio orchestrator (19 pytest)
│   │   ├── app/
│   │   │   ├── client.py          # asyncio TCP + exponential-backoff reconnect
│   │   │   ├── sequences.py       # YAML drive cycles + SQLite telemetry log
│   │   │   ├── fault_injector.py  # THERMAL_RUNAWAY / SENSOR_DROPOUT / OVERCURRENT
│   │   │   └── main.py            # FastAPI + lifespan
│   │   ├── sequences/             # 4 YAML sequences (CONSTANT_DISCHARGE, ACCEL_PULSE, …)
│   │   └── tests/                 # 19 pytest tests (mock TCP server, no real daemon)
│   ├── cmake/toolchain-arm64.cmake
│   ├── systemd/             #   bms-daemon.service + orchestrator.service
│   ├── scripts/             #   deploy.sh + run-smoke-test.sh
│   └── docs/ev-battery-hil.md     # Architecture · BMS FSM · fault injection · 30-test breakdown
├── slm_sensor_analytics/    # ── SLM Machine Sensor Analytics ──────────
│   ├── app/
│   │   ├── api/v1/          #   REST routes and schemas
│   │   ├── db/              #   SQLAlchemy models + async session
│   │   ├── repositories/    #   SensorReadingRepository · AlertRepository
│   │   ├── services/        #   FeatureExtractor (mean/std/RMS/P2P/kurtosis) · IsolationForest
│   │   └── main.py
│   ├── migrations/          #   Alembic DB migrations
│   ├── tests/               #   26 pytest tests (aiosqlite in-memory)
│   ├── Dockerfile
│   ├── docker-compose.yml   #   app + PostgreSQL
│   └── docs/slm-sensor-analytics.md  # Architecture · feature math table · 26-test breakdown
├── fleet_routing_api/       # ── Secure Logistics Fleet Routing API ─────────
│   ├── app/
│   │   ├── auth/            #   JWT HS256 — token issue + dispatcher role gate
│   │   ├── api/             #   auth / deliveries / routes routers
│   │   ├── db/              #   SQLAlchemy: Vehicle · Driver · Delivery · Waypoint (FK cascade)
│   │   └── routing/         #   haversine.py · optimizer.py (nearest-neighbour VRP, O(n²))
│   ├── tests/               #   24 pytest tests — 94.5% coverage, SQLite override
│   ├── docs/
│   │   ├── fleet-routing-api.md   # Architecture · Haversine formula · VRP · 24-test breakdown
│   │   └── ROUTING-MATH.md        # Full formula derivation + complexity analysis
│   ├── Dockerfile
│   └── docker-compose.yml   #   API + PostgreSQL 16 + Redis 7
├── aws_sensor_api/          # ── Cloud-Native Python Backend on AWS ─────────
│   ├── app/
│   │   ├── db/              #   SensorEvent ORM + async session
│   │   ├── main.py          #   FastAPI — POST /api/v1/events · GET list + by-id · /health · /metrics
│   │   ├── repository.py    #   EventRepository — insert · list(filter/paginate) · set_s3_key
│   │   ├── schemas.py       #   Pydantic v2 — SensorEventCreate · Response · Paginated
│   │   └── archival.py      #   S3Archiver — boto3/asyncio.to_thread fire-and-forget
│   ├── tests/               #   15 pytest — moto @mock_aws · aiosqlite · ASGITransport (93% cov)
│   ├── terraform/           #   4 modules: vpc · ecs · rds · s3_iam + S3 remote state
│   │   └── modules/
│   │       ├── vpc/         #   VPC · public+private subnets · NAT gateway
│   │       ├── ecs/         #   Fargate cluster · ECR · ALB · task def · IAM roles
│   │       ├── rds/         #   PostgreSQL 16 · SSM password · private subnet SG
│   │       └── s3_iam/      #   S3 bucket (versioned/AES256/Glacier) · least-privilege policy
│   ├── docker/Dockerfile    #   multi-stage, python:3.12-slim-bookworm
│   ├── pyproject.toml       #   standalone uv project
│   └── docs/aws-sensor-api.md  # Architecture · Terraform modules · boto3/thread rationale
├── renewables_portfolio_dispatch/  # ── Renewables Portfolio Dispatch Optimizer ──
│   ├── app/
│   │   ├── telemetry/router.py    #   POST /api/assets · POST /api/telemetry (bulk 200 rows)
│   │   ├── forecast/
│   │   │   ├── pipeline.py        #   SARIMA(1,1,1)(1,1,0,96) + XGBRegressor(n=100); μ=0.5·exp(ŷ_s)+0.5·ŷ_x
│   │   │   ├── router.py          #   POST /api/forecast/{asset_id} → BackgroundTasks
│   │   │   └── tasks.py           #   Celery shared_task _run_forecast_async
│   │   ├── optimizer/
│   │   │   ├── dispatch.py        #   DispatchOptimiser — CVXPY LP + OSQP; cp.norm L1 netting
│   │   │   └── router.py          #   POST /api/schedule/optimise (201) → persists Schedule rows
│   │   ├── fahrplan/
│   │   │   ├── schemas.py         #   Fahrplan {UUID, portfolio_id, date, intervals} · ScheduleInterval
│   │   │   ├── router.py          #   POST/GET/PATCH /api/fahrplan/{schedule_id}
│   │   │   └── blob_store.py      #   BlobStore Protocol: AzureBlobStore / NullBlobStore
│   │   ├── reopt/worker.py        #   Redis Pub/Sub subscriber + intraday_reforecast Celery task
│   │   └── models/{orm,schemas}.py
│   ├── migrations/versions/001_initial_schema.py  # create_hypertable DO block
│   ├── tests/                     #   25 pytest-asyncio (24 pass + 1 TimescaleDB skip locally)
│   │   ├── conftest.py            #   SQLite client + pg_client (real PG + hypertable setup)
│   │   ├── test_telemetry.py      #   6 tests: assets · bulk ingest · over-capacity · TimescaleDB chunks
│   │   ├── test_forecast.py       #   5 tests: MAPE<8% · endpoint · non-negative · ensemble · DB save
│   │   ├── test_optimizer.py      #   8 tests: LP feasibility · ramp · netting · infeasible · Fahrplan CRUD
│   │   └── test_reopt.py          #   6 tests: cycle<30s · stale guard · channel subscribe · deviation
│   ├── infra/main.bicep           #   Container Apps + PostgreSQL Flexible + Redis + Blob Storage
│   ├── Dockerfile                 #   builder (uv sync) + runtime (non-root appuser)
│   ├── docker-compose.yml         #   timescale/timescaledb:latest-pg16 · redis · forecast-api · celery
│   └── pyproject.toml             #   cvxpy · statsmodels · xgboost · scikit-learn · celery · redis
└── .github/workflows/
    ├── ci.yml                    # Dosing controller CI + aws-sensor-api-test (15 pytest, moto)
    ├── ev-battery-hil.yml        # EV Battery HIL CI (python-lint + python-test + ARM64)
    └── fleet-routing-api.yml     # Fleet Routing API CI (flake8 + pytest, SQLite)
```

---

## Quick Start

### Run the full stack locally (Docker)

```bash
# Start C++ daemon (requires libmodbus)
cd controller
cmake -B build -S . -DCMAKE_BUILD_TYPE=Release
cmake --build build -j4
./build/dosing_daemon  # listens on port 5502

# In a second terminal — spin up Python stack
docker compose up --build
```

- Dashboard: http://localhost:80
- REST API: http://localhost:8092/api/status

### Deploy to Raspberry Pi (one command)

```bash
# Edit inventory/rpi.ini with your Pi's IP and SSH user
ansible-playbook -i ansible/inventory/rpi.ini ansible/site.yml
```

The playbook installs Docker, cross-compiles the C++ daemon, deploys the systemd unit, and starts the Docker stack.

### EV Battery HIL Test Simulator

```bash
# Build BMS C++ daemon (native x86_64)
cmake -B ev_battery_hil/bms/build -S ev_battery_hil/bms -DCMAKE_BUILD_TYPE=Release
cmake --build ev_battery_hil/bms/build -j$(nproc)
ctest --test-dir ev_battery_hil/bms/build --output-on-failure -V   # 11 GoogleTests

# ARM64 cross-compile (Raspberry Pi 4 / i.MX 8M)
sudo apt-get install gcc-aarch64-linux-gnu g++-aarch64-linux-gnu
cmake -B ev_battery_hil/bms/build-arm64 -S ev_battery_hil/bms \
  -DCMAKE_TOOLCHAIN_FILE=ev_battery_hil/cmake/toolchain-arm64.cmake \
  -DBUILD_TESTING=OFF
cmake --build ev_battery_hil/bms/build-arm64 --target bms_daemon -j$(nproc)

# Run Python orchestrator tests (no real daemon — mock TCP server)
cd ev_battery_hil && uv run pytest orchestrator/ -v   # 19 pytest

# Run the full stack
./ev_battery_hil/bms/build/bms_daemon 5555 &
cd ev_battery_hil && BMS_HOST=localhost BMS_PORT=5555 \
  uv run uvicorn orchestrator.app.main:app --port 8080
```

### SLM Machine Sensor Analytics

```bash
# Run tests (aiosqlite in-memory, no Docker required)
PYTHONPATH=slm_sensor_analytics uv run pytest slm_sensor_analytics -v   # 26 pytest

# Full stack (FastAPI + PostgreSQL)
cd slm_sensor_analytics && docker compose up -d
# Swagger UI: http://localhost:8001/docs
# Metrics:    http://localhost:8001/api/v1/metrics

# Ingest → train → predict
curl -X POST http://localhost:8001/api/v1/ingest \
  -H "Content-Type: application/json" \
  -d '{"device_id":"CNC-01","sensor_type":"vibration","values":[0.1,0.2,0.15],"timestamp":"2026-01-15T08:00:00Z"}'
curl -X POST "http://localhost:8001/api/v1/train?device_id=CNC-01&sensor_type=vibration"
curl -X POST "http://localhost:8001/api/v1/predict?device_id=CNC-01&sensor_type=vibration"
```

### Secure Logistics Fleet Routing API

```bash
# Run tests (SQLite in-memory, no Docker required)
cd fleet_routing_api && uv run pytest tests/ -v   # 24 pytest at 94.5% coverage

# Full stack (FastAPI + PostgreSQL + Redis)
cd fleet_routing_api && docker compose up -d
# Swagger UI: http://localhost:8000/docs

# Get a dispatcher token and optimise a route
TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/token \
  -H "Content-Type: application/json" \
  -d '{"username":"dispatcher1","password":"dispatch123"}' | python3 -c "import sys,json;print(json.load(sys.stdin)['access_token'])")
curl -X POST http://localhost:8000/api/v1/routes \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"depot_lat":51.5074,"depot_lon":-0.1278,"waypoints":[{"id":1,"lat":48.8566,"lon":2.3522},{"id":2,"lat":52.5200,"lon":13.4050}]}'
```

### Renewables Portfolio Dispatch Optimizer

```bash
# Run tests (SQLite in-memory — no real PostgreSQL or Redis needed)
cd renewables_portfolio_dispatch
uv sync
uv run pytest tests/ -v   # 24 pass + 1 TimescaleDB skip

# Full stack (TimescaleDB + Redis + Celery)
docker compose up -d
# API docs: http://localhost:8000/docs

# Ingest an asset and trigger a forecast
curl -X POST http://localhost:8000/api/assets \
  -H "Content-Type: application/json" \
  -d '{"name":"Wind-Farm-1","type":"wind","capacity_mw":100.0,"ramp_rate_mw_per_min":5.0}'
curl -X POST http://localhost:8000/api/forecast/1

# Optimise a daily dispatch schedule
curl -X POST http://localhost:8000/api/schedule/optimise \
  -H "Content-Type: application/json" \
  -d '{"portfolio_id":1,"date":"2026-06-03","asset_ids":[1],"price_curve_eur_mwh":[50.0,52.0,48.0,55.0,60.0,58.0,54.0,50.0,46.0,44.0,42.0,43.0,45.0,47.0,50.0,53.0,56.0,59.0,61.0,63.0,62.0,60.0,57.0,54.0]}'

# Run with live TimescaleDB chunks test
USE_TIMESCALEDB=1 \
  DATABASE_URL=postgresql+asyncpg://dispatch:dispatch@localhost:5432/dispatch \
  uv run pytest tests/test_telemetry.py::test_hypertable_partitioning_query -v
```

### Cloud-Native Python Backend on AWS

```bash
# Run tests (no real AWS needed — moto + aiosqlite)
cd aws_sensor_api && uv run pytest tests/ -v   # 15 pytest at 93% coverage

# Run locally (SQLite for dev)
cd aws_sensor_api
DATABASE_URL=sqlite+aiosqlite:///./dev.db S3_BUCKET=local-test \
  uv run uvicorn app.main:app --reload --port 8080

# Provision AWS infrastructure
cd aws_sensor_api/terraform
terraform init
terraform plan -var env=dev
terraform apply -var env=dev

# Post a sensor event
curl -X POST http://<alb-dns>/api/v1/events \
  -H "Content-Type: application/json" \
  -d '{"plant_id":"PLT-001","sensor_id":"TEMP-A","timestamp":"2026-01-15T08:00:00Z","value":85.3,"unit":"°C"}'
```

---

## Tests

### C++ — 13 GoogleTests (`dosing_core`, no Modbus required)

| Suite            | Test                            | What it verifies                         |
|------------------|---------------------------------|------------------------------------------|
| RfidSimulatorTest | PoolHasCorrectSize             | 8 EPC strings in pool                    |
| RfidSimulatorTest | EpcIs16Chars                   | All EPCs are exactly 16 hex characters   |
| RfidSimulatorTest | InjectTagReturnedOnNextScan    | `inject()` forces a specific tag read    |
| RfidSimulatorTest | InjectedTagClearedAfterOneScan | Injected tag is one-shot                 |
| FlowSensorTest   | ZeroTargetProducesLowFlow      | Flow below low threshold when target = 0 |
| FlowSensorTest   | NominalTargetIsFlowing         | Flow above low threshold at nominal rate  |
| DosingFsmTest    | StartsIdle                     | FSM initialises in IDLE state            |
| DosingFsmTest    | IdleToDosingOnValveAndRfid     | IDLE → DOSING when valve=1 and RFID seen |
| DosingFsmTest    | IdleStaysIdleWithoutRfid       | Valve alone does not start dosing        |
| DosingFsmTest    | DosingToPauseOnValveClose      | DOSING → PAUSE when valve=0              |
| DosingFsmTest    | AccumulatesVolumeWhileDosing   | Volume increments correctly in DOSING    |
| DosingFsmTest    | CompletesWhenTargetReached     | DOSING → COMPLETE at target volume       |
| DosingFsmTest    | ResetFromComplete              | reset_cmd=1 returns any state to IDLE    |

```bash
cd controller
cmake -B build -S . -DCMAKE_BUILD_TYPE=Debug
cmake --build build -j4
ctest --test-dir build --output-on-failure -V
```

### Python — 14 pytest tests (no daemon, no Modbus)

| Module          | Test                                  | What it verifies                          |
|-----------------|---------------------------------------|-------------------------------------------|
| test_collector  | test_parse_flow_rate                  | Register 0 → ml/min fixed-point decode    |
| test_collector  | test_parse_valve_state                | Register 1 → bool                        |
| test_collector  | test_parse_dosing_state_dosing        | Register 12 → DosingState enum            |
| test_collector  | test_parse_total_volume               | Registers 2-3 → uint32 big-endian         |
| test_collector  | test_parse_too_few_registers_raises   | ValueError on short register list         |
| test_collector  | test_state_name_mapping               | Integer → state name string               |
| test_collector  | test_write_metric_persists            | SQLite row written and re-readable        |
| test_api        | test_health                           | GET /health returns `{"status":"ok"}`     |
| test_api        | test_status_empty_db                  | Empty DB returns no-data message          |
| test_api        | test_status_returns_latest_row        | Latest sensor_metrics row returned        |
| test_api        | test_events_empty                     | Empty dosing_events returns `[]`          |
| test_api        | test_metrics_limit                    | `?last_n=3` returns exactly 3 rows        |
| test_api        | test_plc_decide_valve_opens_when_flow_ok | valve opens at sufficient flow + DOSING |
| test_api        | test_plc_decide_valve_closes_when_complete | valve closes in COMPLETE state        |

```bash
uv sync --frozen
uv run pytest tests/ -v --tb=short
```

---

## CI

### Dosing Controller (`.github/workflows/ci.yml`)

| Job                    | Runner        | What it does                                             |
|------------------------|---------------|----------------------------------------------------------|
| `lint`                 | ubuntu-latest | ruff check + ruff format on all Python                   |
| `aws-sensor-api-test`  | ubuntu-latest | 15 pytest — moto S3 + aiosqlite + ASGITransport (93% cov) |
| `python-tests`         | ubuntu-latest | 14 pytest tests (in-memory SQLite, no daemon)            |
| `cpp-build-test`       | ubuntu-latest | CMake build + 13 GoogleTests with libmodbus from apt     |
| `arm64-cross-build`    | ubuntu-latest | Cross-compile `dosing_core` for aarch64 (no libmodbus)   |

### EV Battery HIL (`.github/workflows/ev-battery-hil.yml`) — triggers on `ev_battery_hil/**`

| Job                 | Runner        | What it does                                              |
|---------------------|---------------|-----------------------------------------------------------|
| `python-lint`       | ubuntu-latest | ruff check + ruff format on orchestrator/                 |
| `python-test`       | ubuntu-latest | 19 pytest tests (mock TCP server, no daemon needed)       |
| `cpp-cross-compile` | ubuntu-latest | Cross-compile `bms_daemon` for ARM64, upload artifact     |

### Fleet Routing API (`.github/workflows/fleet-routing-api.yml`) — triggers on `fleet_routing_api/**`

| Job     | Runner        | What it does                                                    |
|---------|---------------|-----------------------------------------------------------------|
| `lint`  | ubuntu-latest | flake8 (max-line-length=100) on app/ and tests/                 |
| `test`  | ubuntu-latest | 24 pytest tests — SQLite override, ≥90% coverage enforced      |

### Renewables Dispatch (root `ci.yml`) — job `renewables-dispatch-test`

| Step | Runner | What it does |
|---|---|---|
| ruff lint + format check | ubuntu-latest | `ruff check` + `ruff format --check` on app/ tests/ |
| mypy | ubuntu-latest | `mypy app/` — typed defs enforced; third-party overrides for cvxpy/celery/redis |
| 25 pytest-asyncio | ubuntu-latest | Service containers: `timescale/timescaledb:latest-pg16` + `redis:7-alpine`; `USE_TIMESCALEDB=1` enables hypertable chunk test |

---

## Tech Stack

| Layer        | Technology                              |
|--------------|-----------------------------------------|
| C++ daemon   | C++17, CMake, libmodbus, systemd notify |
| Fieldbus     | Modbus TCP (IEC 61158), port 5502       |
| PLC emulator | Python, pymodbus                        |
| Persistence  | SQLite 3 (WAL mode)                     |
| REST API     | Python, FastAPI, uvicorn                |
| Dashboard    | Vanilla JS, Chart.js, nginx             |
| DevOps       | Docker Compose, Ansible, GitHub Actions, Terraform |
| Cloud        | AWS ECS Fargate, RDS PostgreSQL 16, S3, ECR, ALB; Azure Container Apps, PostgreSQL Flexible Server, Redis Cache, Blob Storage |
| Energy ML    | statsmodels SARIMAX, XGBoost, scikit-learn, CVXPY/OSQP LP solver, pandas, numpy |
| Event-driven | Celery 5.3 (Redis broker), Redis Pub/Sub, fakeredis |
| Time-series  | TimescaleDB hypertable (7-day chunks), Alembic async migrations |
| IaC          | Terraform (AWS), Azure Bicep                        |
| Targets      | x86_64 (CI/dev), ARM64 (Raspberry Pi 4)            |
