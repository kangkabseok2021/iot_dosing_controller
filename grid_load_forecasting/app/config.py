from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+asyncpg://grid:grid@localhost:5432/griddb"
    MAX_BATCH_SIZE: int = 1000
    SMA_WINDOW_SIZE: int = 12
    LOG_LEVEL: str = "INFO"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
