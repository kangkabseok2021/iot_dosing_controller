#!/usr/bin/env python3
"""Plot a 3-panel thermal runaway timeline from orchestrator event log."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


def _load_events(path: str) -> list[dict]:
    events = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return events


def plot(log_path: str = "orchestrator.log",
         out: str = "docs/images/thermal-runaway-timeline.png") -> None:
    events = _load_events(log_path)

    times: list[float] = []
    temps: list[float] = []
    currents: list[float] = []
    socs: list[float] = []
    fault_time: float | None = None
    warn_time: float | None = None

    for evt in events:
        tel = evt.get("telemetry_snapshot")
        if not tel:
            continue
        t = float(evt.get("elapsed_s", len(times)))
        times.append(t)
        temps.append(tel.get("T_cell", 0.0))
        currents.append(tel.get("I_load", 0.0))
        socs.append(tel.get("SoC", 0.0))
        if tel.get("state") == "FAULT" and fault_time is None:
            fault_time = t
        if tel.get("T_cell", 0) >= 60.0 and warn_time is None:
            warn_time = t

    if not times:
        print("No telemetry data found — run a THERMAL_RUNAWAY fault injection first.")
        sys.exit(1)

    fig, axes = plt.subplots(3, 1, figsize=(12, 8), sharex=True)
    fig.suptitle("Thermal Runaway — EV Battery HIL (THERMAL-RUNAWAY-001)", fontsize=13)

    ax0 = axes[0]
    ax0.plot(times, temps, "r-", linewidth=1.5, label="T_cell (°C)")
    ax0.axhline(60, color="orange", linestyle="--", linewidth=1, label="WARN 60°C")
    ax0.axhline(80, color="darkred", linestyle="--", linewidth=1, label="FAULT 80°C")
    if warn_time is not None:
        ax0.axvline(warn_time, color="orange", linestyle=":", alpha=0.8)
    if fault_time is not None:
        ax0.axvline(fault_time, color="darkred", linestyle=":", alpha=0.8)
    ax0.set_ylabel("Temperature (°C)")
    ax0.legend(loc="upper left", fontsize=9)

    axes[1].plot(times, currents, "b-", linewidth=1.5)
    axes[1].set_ylabel("I_load (A)")

    axes[2].plot(times, socs, "g-", linewidth=1.5)
    if fault_time is not None:
        axes[2].axvline(fault_time, color="darkred", linestyle=":",
                        alpha=0.8, label=f"FAULT at {fault_time:.0f}s")
        axes[2].legend(loc="upper right", fontsize=9)
    axes[2].set_ylabel("SoC")
    axes[2].set_xlabel("Elapsed (s)")

    plt.tight_layout()
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(out, dpi=150)
    print(f"Saved: {out}")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Plot thermal runaway timeline")
    p.add_argument("--log", default="orchestrator.log")
    p.add_argument("--out", default="docs/images/thermal-runaway-timeline.png")
    args = p.parse_args()
    plot(args.log, args.out)
