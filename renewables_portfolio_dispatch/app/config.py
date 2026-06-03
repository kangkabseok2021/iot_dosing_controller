from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://dispatch:dispatch@localhost:5432/dispatch"
    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "redis://localhost:6379/1"
    celery_result_backend: str = "redis://localhost:6379/2"
    azure_storage_connection_string: str = ""
    azure_storage_container: str = "fahrplan-archive"
    imbalance_penalty: float = 10.0
    deviation_threshold_pct: float = 0.05

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
