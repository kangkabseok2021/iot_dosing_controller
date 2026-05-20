import asyncio
import logging
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import aiosqlite
import yaml

from .client import OrchestratorClient
from .models import TelemetryFrame

log = logging.getLogger(__name__)

_SEQUENCES_DIR = Path(__file__).parent.parent / "sequences"
_DB_PATH = "runs.db"


async def _ensure_db() -> None:
    async with aiosqlite.connect(_DB_PATH) as db:
        await db.execute(
            """CREATE TABLE IF NOT EXISTS telemetry_snapshots (
                run_id TEXT, seq_id TEXT, ts_us INTEGER,
                soc REAL, v_terminal REAL, i_load REAL, t_cell REAL, state TEXT
            )"""
        )
        await db.commit()


async def _log_snapshot(run_id: str, seq_id: str, frame: Optional[TelemetryFrame]) -> None:
    if frame is None:
        return
    async with aiosqlite.connect(_DB_PATH) as db:
        await db.execute(
            "INSERT INTO telemetry_snapshots VALUES (?,?,?,?,?,?,?,?)",
            (run_id, seq_id, frame.ts_us, frame.SoC,
             frame.V_terminal, frame.I_load, frame.T_cell, frame.state),
        )
        await db.commit()


@dataclass
class SequenceRun:
    seq_id: str
    running: bool = False
    elapsed_s: float = 0.0
    last_telemetry: Optional[TelemetryFrame] = None
    passed: bool = False
    run_id: str = field(default_factory=lambda: str(uuid.uuid4()))


class SequenceEngine:
    def __init__(self, client: OrchestratorClient) -> None:
        self._client = client
        self._runs: dict[str, SequenceRun] = {}

    def load_sequence(self, seq_id: str) -> dict:
        path = _SEQUENCES_DIR / f"{seq_id.lower()}.yaml"
        if not path.exists():
            raise ValueError(f"Unknown sequence: {seq_id}")
        with open(path) as f:
            return yaml.safe_load(f)

    async def start(self, seq_id: str) -> None:
        spec = self.load_sequence(seq_id)
        run = SequenceRun(seq_id=seq_id, running=True)
        self._runs[seq_id] = run
        asyncio.create_task(self._run(spec, run))

    async def _run(self, spec: dict, run: SequenceRun) -> None:
        await _ensure_db()
        repeat = spec.get("repeat", 1)
        t0 = asyncio.get_event_loop().time()
        try:
            for _ in range(repeat):
                for step in spec["steps"]:
                    await self._client.send_command(
                        step["command"], step.get("value")
                    )
                    await asyncio.sleep(step.get("duration_s", 0))
                    run.last_telemetry = self._client.last_frame
                    await _log_snapshot(run.run_id, run.seq_id, run.last_telemetry)
            run.passed = True
        except Exception as exc:
            log.error("Sequence %s failed: %s", run.seq_id, exc)
        finally:
            run.elapsed_s = asyncio.get_event_loop().time() - t0
            run.running = False
            await self._client.send_command("SET_CURRENT", 0.0)

    def status(self, seq_id: str) -> Optional[SequenceRun]:
        return self._runs.get(seq_id)
