from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file="../.env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = "postgresql+asyncpg://biletflow:biletflow@localhost:5432/biletflow"
    jwt_secret: str = "change-me-in-dev"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    web_base_url: str = "http://localhost:5173"
    smtp_host: str = "localhost"
    smtp_port: int = 1025
    smtp_from: str = "no-reply@biletflow.local"


@lru_cache
def get_settings() -> Settings:
    return Settings()
