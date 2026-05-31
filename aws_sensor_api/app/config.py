from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://apiuser:secret@localhost:5432/sensordb"
    s3_bucket: str = "oem-sensor-events"
    aws_region: str = "eu-central-1"
    log_level: str = "INFO"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
