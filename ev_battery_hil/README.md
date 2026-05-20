# EV Battery HIL Test Simulator

HIL test automation platform for an EV Battery Management System. A **C++17 daemon** runs a Thevenin 1-RC equivalent circuit model at 1 kHz, streams live telemetry over TCP at 100 Hz, and accepts load commands on the same connection. A **Python asyncio orchestrator** connects as the test automation platform, runs structured drive-cycle sequences, injects repeatable faults, and serves all controls via a FastAPI REST API.

---

## Architecture

```
C++ BMS Daemon (TCP :5555)
  └── BatteryModel      — Thevenin ECM + RK4 @ 1 kHz
  └── BmsStateMachine   — IDLE→DISCHARGING→CHARGING→FAULT (latching)
  └── TelemetryServer   — JSON frames @ 100 Hz + line-delimited commands

Python Orchestrator (HTTP :8080)
  └── OrchestratorClient  — asyncio TCP, exponential-backoff reconnect
  └── SequenceEngine      — YAML drive cycles + SQLite telemetry log
  └── FaultInjector       — THERMAL_RUNAWAY / SENSOR_DROPOUT / OVERCURRENT
  └── FastAPI             — /api/status · /api/command · /api/sequences · /api/faults
```

---

## Building the BMS Daemon

### Native (x86, for testing)
```bash
cmake -B bms/build -S bms -DCMAKE_BUILD_TYPE=Release
cmake --build bms/build -j4
./bms/build/bms_daemon 5555
```

### ARM64 (Raspberry Pi 4 / i.MX 8M)
```bash
cmake -B bms/build-arm64 -S bms \
  -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_TOOLCHAIN_FILE=cmake/toolchain-arm64.cmake \
  -DBUILD_TESTING=OFF
cmake --build bms/build-arm64 --target bms_daemon -j4
# Deploy to device:
TARGET_HOST=<device-ip> ./scripts/deploy.sh
```

### GoogleTests (11 tests)
```bash
cmake -B bms/build -S bms -DCMAKE_BUILD_TYPE=Debug -DBUILD_TESTING=ON
cmake --build bms/build && ctest --test-dir bms/build -V
```

---

## Running the Python Orchestrator

```bash
cd ev_battery_hil
uv sync
BMS_HOST=localhost BMS_PORT=5555 uv run uvicorn orchestrator.app.main:app --port 8080
```

Install as systemd services (ARM64 device):
```bash
sudo cp systemd/bms-daemon.service /etc/systemd/system/
sudo cp systemd/orchestrator.service /etc/systemd/system/
sudo systemctl enable --now bms-daemon orchestrator
```

---

## Running Test Sequences

```bash
# Start a sequence
curl -X POST http://localhost:8080/api/sequences/ACCELERATION_PULSE/start

# Poll status
curl http://localhost:8080/api/sequences/ACCELERATION_PULSE/status

# Check BMS telemetry
curl http://localhost:8080/api/status
```

Available sequences: `CONSTANT_DISCHARGE` · `ACCELERATION_PULSE` · `REGEN_BRAKING` · `CAPACITY_TEST`

---

## Fault Injection

```bash
# Thermal runaway (blocks cooling vent → WARN at ~35s, FAULT at ~55s)
curl -X POST http://localhost:8080/api/faults/inject \
     -H "Content-Type: application/json" \
     -d '{"fault_type":"THERMAL_RUNAWAY"}'

# Reset after fault
curl -X POST http://localhost:8080/api/command \
     -H "Content-Type: application/json" \
     -d '{"command":"RESET"}'

# Sensor dropout (closes TCP for 5s, client reconnects automatically)
curl -X POST http://localhost:8080/api/faults/inject \
     -H "Content-Type: application/json" \
     -d '{"fault_type":"SENSOR_DROPOUT","params":{"duration_s":5}}'

# Overcurrent (300 A > 250 A limit, daemon rejects with FAULT)
curl -X POST http://localhost:8080/api/faults/inject \
     -H "Content-Type: application/json" \
     -d '{"fault_type":"OVERCURRENT"}'
```

---

## Reproducing the Troubleshooting Report

```bash
# 1. Start daemon
./bms/build/bms_daemon 5555 &
# 2. Start orchestrator
BMS_HOST=localhost uv run uvicorn orchestrator.app.main:app --port 8080 &
# 3. Inject thermal runaway
curl -X POST http://localhost:8080/api/faults/inject \
     -d '{"fault_type":"THERMAL_RUNAWAY"}'
# 4. Wait ~60s for FAULT, then plot
uv run python orchestrator/tools/plot_fault_timeline.py \
     --log orchestrator.log \
     --out docs/images/thermal-runaway-timeline.png
# 5. View report
open docs/fault-report-THERMAL-RUNAWAY-001.md
```

See [`docs/fault-report-THERMAL-RUNAWAY-001.md`](docs/fault-report-THERMAL-RUNAWAY-001.md) for the full root-cause analysis.

---

## Smoke Test (deployed device)

```bash
TARGET_HOST=192.168.1.10 ./scripts/run-smoke-test.sh
```

Expected: `SoC delta: 0.008... — PASS`

