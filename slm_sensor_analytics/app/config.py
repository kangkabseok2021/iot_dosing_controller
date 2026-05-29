from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+asyncpg://slm:slm@localhost:5432/slmdb"
    ANOMALY_THRESHOLD: float = -0.1
    MODEL_DIR: str = "models"
    LOG_LEVEL: str = "INFO"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
