from fastapi import FastAPI

from app.api import auth, deliveries, routes


def create_app() -> FastAPI:
    app = FastAPI(title="Secure Logistics Fleet Routing API", version="0.1.0")
    app.include_router(auth.router)
    app.include_router(deliveries.router)
    app.include_router(routes.router)
    return app


app = create_app()
