# IoT Dosing Controller, EV Battery HIL Simulator, Machine Sensor Analytics & Fleet Routing API

A collection of industrial IoT, predictive maintenance, and logistics systems sharing edge daemon architectures, asyncio orchestration, and machine learning telemetry pipelines.

| Project | Description | Docs |
|---|---|---|
| **Edge IoT Dosing Controller** | C++17 Modbus TCP daemon + Python PLC simulator + FastAPI dashboard — deploys to Raspberry Pi 4 via Ansible | [Architecture ↓](#architecture) |
| **EV Battery HIL Test Simulator** | C++17 Thevenin ECM battery daemon + Python asyncio orchestrator with FastAPI, fault injection, and GitHub Actions ARM64 CI | [ev_battery_hil/README.md](ev_battery_hil/README.md) |
| **SLM Machine Sensor Analytics** | Multi-sensor telemetry ingestion, statistical feature extraction (RMS/Kurtosis), and Isolation Forest anomaly detection API | [slm_sensor_analytics/README.md](slm_sensor_analytics/README.md) |
| **Secure Logistics Fleet Routing API** | FastAPI + JWT RBAC + Haversine O(n²) VRP optimizer + Redis route cache (TTL 300 s) + SQLAlchemy fleet schema — 24 pytest tests at 94.5% coverage | [fleet_routing_api/README.md](fleet_routing_api/README.md) |

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
│   │   │   ├── client.py          # asyncio TCP + reconnect
│   │   │   ├── sequences.py       # YAML drive cycles + SQLite log
│   │   │   ├── fault_injector.py  # THERMAL_RUNAWAY / SENSOR_DROPOUT / OVERCURRENT
│   │   │   └── main.py            # FastAPI + lifespan
│   │   ├── sequences/             # 4 YAML test sequences
│   │   └── tests/                 # 19 pytest tests
│   ├── cmake/toolchain-arm64.cmake
│   ├── systemd/             #   bms-daemon.service + orchestrator.service
│   ├── scripts/             #   deploy.sh + run-smoke-test.sh
│   └── README.md
├── slm_sensor_analytics/    # ── SLM Machine Sensor Analytics ──────────
│   ├── app/                 #   FastAPI backend app code
│   │   ├── api/v1/          #     REST routes and schemas
│   │   ├── db/              #     PostgreSQL models and session setup
│   │   ├── repositories/    #     Database repositories
│   │   ├── services/        #     Feature extraction & anomaly models
│   │   └── main.py          #     App initialization
│   ├── migrations/          #   Alembic DB migrations
│   ├── tests/               #   26 pytest tests (SQLite in-memory)
│   ├── Dockerfile           #   Multi-stage build
│   ├── docker-compose.yml   #   Docker compose (app + postgres db)
│   └── README.md            #   Subproject documentation
├── fleet_routing_api/       # ── Secure Logistics Fleet Routing API ─────────
│   ├── app/
│   │   ├── auth/            #   JWT HS256 — create/decode tokens, dispatcher gate
│   │   ├── api/             #   auth / deliveries / routes routers
│   │   ├── db/              #   SQLAlchemy models: Vehicle, Driver, Delivery, Waypoint
│   │   └── routing/         #   haversine.py + optimizer.py (nearest-neighbour VRP)
│   ├── tests/               #   24 pytest tests (94.5% coverage, SQLite override)
│   ├── docs/ROUTING-MATH.md #   Haversine derivation + O(n²) complexity + optimality gap
│   ├── Dockerfile           #   Multi-stage build
│   ├── docker-compose.yml   #   API + PostgreSQL 16 + Redis 7
│   └── README.md
└── .github/workflows/
    ├── ci.yml                    # Dosing controller CI
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

| Job               | Runner        | What it does                                             |
|-------------------|---------------|----------------------------------------------------------|
| `lint`            | ubuntu-latest | ruff check + ruff format on all Python                   |
| `python-tests`    | ubuntu-latest | 14 pytest tests (in-memory SQLite, no daemon)            |
| `cpp-build-test`  | ubuntu-latest | CMake build + 13 GoogleTests with libmodbus from apt     |
| `arm64-cross-build` | ubuntu-latest | Cross-compile `dosing_core` for aarch64 (no libmodbus) |

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
| DevOps       | Docker Compose, Ansible, GitHub Actions |
| Targets      | x86_64 (CI/dev), ARM64 (Raspberry Pi 4)|
