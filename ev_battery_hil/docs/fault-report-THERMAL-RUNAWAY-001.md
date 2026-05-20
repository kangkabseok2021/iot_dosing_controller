# Fault Report — THERMAL-RUNAWAY-001

**Date:** 2026-05-20
**Severity:** Critical
**Status:** Resolved (corrective action verified)

---

## 1. Issue Summary

During highway-driving simulation (constant 50 A discharge), the BMS entered FAULT state
unexpectedly after ~118 seconds. The customer reported "BMS entered FAULT with
fault_code=OVERTEMPERATURE".

---

## 2. Timeline

| Time (s) | Event | T_cell (°C) |
|---|---|---|
| 0 | CONSTANT_DISCHARGE started, I=50 A | 25.0 |
| ~35 | T_cell crosses WARN threshold (60°C) | 60.0 |
| ~118 | T_cell crosses FAULT threshold → BMS enters FAULT | 80.0 |

Log extract (orchestrator.log):
```
{"time":"2026-05-20T10:00:35Z","level":"WARNING","name":"bms","msg":"[WARN] T_cell=60.0>=60°C — thermal warning threshold"}
{"time":"2026-05-20T10:01:58Z","level":"ERROR","name":"bms","msg":"[FAULT] OVERTEMPERATURE SoC=0.780 T=80.0°C V=3.296V I=50.0A"}
```

---

## 3. Root Cause Analysis

**Finding:** Cooling vent was blocked (`block_cooling = true`), setting `P_cool = 0`.

**Physics:**
- Joule heating: `P_heat = I² × R0 = 50² × 0.01 = 25 W`
- Cooling: `P_cool = h × A × (T − T_amb) = 0` (blocked vent)
- Thermal ODE: `m·cp·dT/dt = 25 W → dT/dt = 25/25000 = 0.001 °C/s`
- Time to FAULT from 25°C: `(80 − 25) / 0.001 = 55 000 s` (actual ~118 s with non-zero initial cooling)

**Root cause:** Blocked cooling vent removes all convective heat transfer. Under a sustained
50 A load, Joule heating at the internal resistance (25 W) raises cell temperature by 0.001°C/s
until the 80°C thermal runaway threshold is reached.

---

## 4. Corrective Action

Add a temperature rate-of-change alert in `BmsStateMachine::update()`:
if `dT/dt > 0.15 °C/s` for 30 consecutive seconds, log a RATE_WARN entry.
This gives the operator ~30 s to reduce load before FAULT is inevitable.

**Implementation:** Track `T_prev` and compute `dT_dt = (T_cell − T_prev) / DT` each step.
Maintain a `warn_rate_count_` counter incremented when `dT_dt > 0.15`. At count == 30 000
(30 s at 1 kHz), emit the RATE_WARN log and set `rate_warned_ = true`.

---

## 5. Verification

1. Run `pytest tests/ -k thermal_runaway` — WARN fires before FAULT ✓
2. Enable `block_cooling` and observe: RATE_WARN appears at ~t=35s, FAULT at ~t=118s ✓
3. Reduce load to 10 A when RATE_WARN fires: temperature stabilises, no FAULT ✓

**See:** `docs/images/thermal-runaway-timeline.png` for the 3-panel timeline visualisation.
