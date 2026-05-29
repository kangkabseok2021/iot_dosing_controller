from contextlib import asynccontextmanager

from fastapi import FastAPI
from loguru import logger
from prometheus_client import make_asgi_app

from app.api.v1.routes import router
from app.config import settings
from app.services.anomaly import ModelStore


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(
        "Starting SLM Machine Sensor Analytics API — log_level={}", settings.LOG_LEVEL
    )
    app.state.model_store = ModelStore(settings.MODEL_DIR)
    yield
    logger.info("Shutdown complete")


app = FastAPI(
    title="SLM Machine Sensor Analytics & Predictive Maintenance API",
    version="1.0.0",
    lifespan=lifespan,
)

app.include_router(router)


@app.get("/health")
async def health_check():
    return {"status": "ok"}


metrics_app = make_asgi_app()
app.mount("/api/v1/metrics", metrics_app)
