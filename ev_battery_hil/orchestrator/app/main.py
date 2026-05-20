import logging
import logging.handlers
import os
from collections import deque
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Optional

from fastapi import FastAPI, HTTPException

from .client import OrchestratorClient
from .fault_injector import FaultInjector
from .models import FaultRequest, LoadCommand
from .sequences import SequenceEngine

log = logging.getLogger(__name__)

client: Optional[OrchestratorClient] = None
engine: Optional[SequenceEngine] = None
injector: Optional[FaultInjector] = None

_event_log: deque[dict] = deque(maxlen=1000)


def record_event(component: str, event: str, **kwargs) -> None:
    _event_log.append({
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "component": component,
        "event": event,
        **kwargs,
    })


def _setup_logging() -> None:
    handler = logging.handlers.RotatingFileHandler(
        "orchestrator.log", maxBytes=10 * 1024 * 1024, backupCount=5
    )
    handler.setFormatter(
        logging.Formatter(
            '{"time":"%(asctime)s","level":"%(levelname)s",'
            '"name":"%(name)s","msg":"%(message)s"}'
        )
    )
    logging.getLogger().addHandler(handler)
    logging.getLogger().setLevel(logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    global client, engine, injector
    _setup_logging()
    host = os.environ.get("BMS_HOST", "localhost")
    port = int(os.environ.get("BMS_PORT", "5555"))
    client = OrchestratorClient(host=host, port=port)
    engine = SequenceEngine(client)
    injector = FaultInjector(client)
    await client.start()
    log.info("Orchestrator started — connecting to %s:%d", host, port)
    yield
    await client.stop()
    log.info("Orchestrator stopped")


app = FastAPI(title="EV Battery HIL Orchestrator", lifespan=lifespan)


@app.get("/api/status")
async def get_status():
    if client is None or client.last_frame is None:
        raise HTTPException(503, "No telemetry available")
    return client.last_frame


@app.post("/api/command")
async def post_command(cmd: LoadCommand):
    if client is None:
        raise HTTPException(503, "Not connected")
    await client.send_command(cmd.command, cmd.value)
    record_event("api", "command_sent", command=cmd.command, value=cmd.value)
    return {"ok": True}


@app.post("/api/sequences/{seq_id}/start")
async def start_sequence(seq_id: str):
    if engine is None:
        raise HTTPException(503, "Engine not ready")
    await engine.start(seq_id)
    record_event("api", "sequence_started", seq_id=seq_id)
    return {"started": seq_id}


@app.get("/api/sequences/{seq_id}/status")
async def sequence_status(seq_id: str):
    if engine is None:
        raise HTTPException(503, "Engine not ready")
    run = engine.status(seq_id)
    if run is None:
        raise HTTPException(404, f"Sequence {seq_id} not found or not yet started")
    return {
        "running": run.running,
        "elapsed_s": run.elapsed_s,
        "last_telemetry": run.last_telemetry,
    }


@app.post("/api/faults/inject")
async def inject_fault(body: FaultRequest):
    if injector is None:
        raise HTTPException(503, "Injector not ready")
    await injector.inject(body.fault_type, body.params)
    record_event("api", "fault_injected", fault_type=body.fault_type)
    return {"injected": body.fault_type}


@app.get("/api/logs")
async def get_logs(since: str | None = None):
    entries = list(_event_log)
    if since:
        entries = [e for e in entries if e["timestamp"] >= since]
    return {"logs": entries}
