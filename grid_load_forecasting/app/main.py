from contextlib import asynccontextmanager

from fastapi import FastAPI
from loguru import logger
from prometheus_client import make_asgi_app

from app.api.v1.routes import router
from app.config import settings
from app.workers.forecaster import ForecastWorker

_worker: ForecastWorker | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _worker
    logger.info("Starting Grid Load Forecasting API — log_level={}", settings.LOG_LEVEL)
    _worker = ForecastWorker()
    await _worker.start()
    yield
    if _worker:
        await _worker.stop()
    logger.info("Shutdown complete")


app = FastAPI(
    title="Grid Load Forecasting API",
    version="1.0.0",
    lifespan=lifespan,
)

app.include_router(router)

metrics_app = make_asgi_app()
app.mount("/api/v1/metrics", metrics_app)
