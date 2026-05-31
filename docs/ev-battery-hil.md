# EV Battery HIL Test Simulator

HIL test automation platform for an EV Battery Management System. A C++17 daemon runs a Thevenin 1-RC equivalent circuit model at 1 kHz, streams live telemetry over TCP at 100 Hz, and accepts load commands on the same connection. A Python asyncio orchestrator connects as the test automation platform, runs structured drive-cycle sequences, injects repeatable faults, and serves all controls via FastAPI.

---

## Architecture

```
C++ BMS Daemon  (TCP :5555)
  ├── BatteryModel      — Thevenin 1-RC ECM + RK4 integration @ 1 kHz
  │     SoC(t+dt) = SoC(t) − (I·dt)/(3600·Q)
  │     V_oc = f(SoC) · lookup  |  V_t = V_oc − I·R0 − V_C1
  ├── BmsStateMachine   — IDLE → DISCHARGING → CHARGING → FAULT (latching)
  └── TelemetryServer   — JSON frames @ 100 Hz + line-delimited commands

Python Orchestrator  (HTTP :8080)
  ├── OrchestratorClient  — asyncio TCP + exponential-backoff reconnect
  ├── SequenceEngine      — YAML drive cycles + SQLite telemetry log
  ├── FaultInjector       — THERMAL_RUNAWAY / SENSOR_DROPOUT / OVERCURRENT
  └── FastAPI             — /api/status · /api/command · /api/sequences · /api/faults
```

---

## BMS State Machine

```
        reset_cmd (any state)
              │
    ┌─────────▼──────────┐
    │        IDLE         │◄──────────────────────────────────┐
    └─────────┬──────────┘                                    │
    load_cmd=DISCHARGE                              reset_cmd=1
              │                                               │
    ┌─────────▼──────────┐  SoC < 5% or     ┌───────────────┴──────┐
    │    DISCHARGING      │──overcurrent────► │       FAULT          │
    └─────────┬──────────┘                   │  (latching — reset   │
    load_cmd=CHARGE                           │   required to clear) │
              │                               └──────────────────────┘
    ┌─────────▼──────────┐  SoC > 95%
    │      CHARGING       │──────────────► IDLE
    └────────────────────┘
```

---

## Test Sequences

| Sequence | Description |
|---|---|
| `CONSTANT_DISCHARGE` | Sustained 50 A draw — measures capacity fade |
| `ACCELERATION_PULSE` | 200 A burst × 3 s → recover → repeat (simulates EV launch) |
| `REGEN_BRAKING` | Negative current pulses at 80 A — validates charging state transitions |
| `CAPACITY_TEST` | Full discharge from 100% → 0% SoC at C/5 rate — measures true capacity |

---

## Fault Injection

| Fault | Trigger | Expected outcome |
|---|---|---|
| `THERMAL_RUNAWAY` | Blocks cooling vent simulation | WARN at ~35 s, FAULT at ~55 s |
| `SENSOR_DROPOUT` | Closes TCP for `duration_s` seconds | Client reconnects automatically |
| `OVERCURRENT` | Sends 300 A > 250 A limit | Daemon rejects → FAULT state |

---

## REST API

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/status` | Live telemetry: SoC, voltage, current, temperature, state |
| `POST` | `/api/command` | Send DISCHARGE / CHARGE / RESET / STOP |
| `POST` | `/api/sequences/{name}/start` | Start a named drive-cycle sequence |
| `GET` | `/api/sequences/{name}/status` | Poll sequence progress |
| `POST` | `/api/faults/inject` | Inject a named fault with optional params |

---

## Quick Start

### Build BMS Daemon (native)

```bash
cmake -B bms/build -S bms -DCMAKE_BUILD_TYPE=Release
cmake --build bms/build -j4
./bms/build/bms_daemon 5555
```

### Build for ARM64 (Raspberry Pi 4 / i.MX 8M)

```bash
cmake -B bms/build-arm64 -S bms \
  -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_TOOLCHAIN_FILE=cmake/toolchain-arm64.cmake \
  -DBUILD_TESTING=OFF
cmake --build bms/build-arm64 --target bms_daemon -j4
TARGET_HOST=<device-ip> ./scripts/deploy.sh
```

### Run Python Orchestrator

```bash
cd ev_battery_hil
uv sync
BMS_HOST=localhost BMS_PORT=5555 uv run uvicorn orchestrator.app.main:app --port 8080
```

### Install as systemd services

```bash
sudo cp systemd/bms-daemon.service /etc/systemd/system/
sudo cp systemd/orchestrator.service /etc/systemd/system/
sudo systemctl enable --now bms-daemon orchestrator
```

---

## Testing

```bash
cd ev_battery_hil && uv run pytest orchestrator/ -v
```

**30 tests — no real daemon, no TCP connection.**

| Suite | n | What it validates |
|---|---|---|
| `test_battery_model` | 11 GoogleTests | Thevenin ECM math, RK4 integration, FSM transitions, overcurrent rejection |
| `test_orchestrator` | 19 pytest | Mock TCP server, sequence execution, fault injection, SQLite log, FastAPI endpoints |

**Key mock pattern:**

```python
# Mock TCP server — no real C++ daemon
server = await asyncio.start_server(handle_client, "127.0.0.1", 0)
port = server.sockets[0].getsockname()[1]
client = OrchestratorClient(host="127.0.0.1", port=port)
```
