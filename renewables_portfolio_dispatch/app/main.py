from fastapi import FastAPI

from app.fahrplan.router import router as fahrplan_router
from app.forecast.router import router as forecast_router
from app.optimizer.router import router as optimizer_router
from app.telemetry.router import router as telemetry_router

app = FastAPI(
    title="Renewables Portfolio Dispatch Optimizer",
    description=(
        "SARIMA + XGBoost generation forecasting, "
        "CVXPY LP dispatch optimisation, "
        "and Fahrplan CRUD with Azure Blob archival."
    ),
    version="1.0.0",
)

app.include_router(telemetry_router)
app.include_router(forecast_router)
app.include_router(optimizer_router)
app.include_router(fahrplan_router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
