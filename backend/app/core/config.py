from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file="../.env", env_file_encoding="utf-8", extra="ignore")

    environment: Literal["development", "test", "production"] = "development"
    database_ssl_mode: Literal["disable", "verify-full"] = "disable"
    database_ssl_ca_file: Path | None = None
    database_url: str = "postgresql+asyncpg://biletflow:biletflow@localhost:5432/biletflow"
    jwt_secret: str = "change-me-in-dev-at-least-32-bytes-long"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 30
    email_verify_token_hours: int = 24
    email_verify_resend_cooldown_seconds: int = 60
    password_reset_token_minutes: int = 60
    password_reset_cooldown_seconds: int = 60
    web_base_url: str = "http://localhost:5173"
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]
    rate_limit_login_requests: int = Field(default=30, ge=1)
    rate_limit_promo_requests: int = Field(default=120, ge=1)
    rate_limit_window_seconds: int = Field(default=60, ge=1)
    smtp_host: str = "localhost"
    smtp_port: int = 1025
    smtp_security: Literal["none", "starttls", "ssl"] = "none"
    smtp_username: str | None = None
    smtp_password: SecretStr | None = None
    smtp_from: str = "no-reply@biletflow.local"
    smtp_timeout_seconds: float = Field(default=10, ge=1, le=60)
    media_root: Path = Path(__file__).resolve().parents[2] / "media"
    image_max_bytes: int = 5 * 1024 * 1024

    @model_validator(mode="after")
    def production_boundaries(self):
        if self.environment == "production":
            from urllib.parse import urlparse

            if len(self.jwt_secret) < 32 or self.jwt_secret.startswith(("change-me", "REPLACE_")):
                raise ValueError(
                    "Production requires a unique JWT_SECRET of at least 32 characters."
                )
            if self.database_ssl_mode != "verify-full":
                raise ValueError("Production requires certificate-verified PostgreSQL TLS.")
            origins = [self.web_base_url, *self.cors_origins]
            if not self.cors_origins or any(
                urlparse(v).scheme != "https"
                or not urlparse(v).hostname
                or urlparse(v).username
                or urlparse(v).query
                or urlparse(v).fragment
                for v in origins
            ):
                raise ValueError("Production requires exact HTTPS web and CORS origins.")
            if any(urlparse(v).path not in ("", "/") for v in self.cors_origins):
                raise ValueError("CORS origins must not contain paths.")
            if self.smtp_security == "none":
                raise ValueError("Production SMTP requires verified TLS.")
        return self

    @model_validator(mode="after")
    def secure_smtp_credentials(self):
        if bool(self.smtp_username) != bool(self.smtp_password):
            raise ValueError("SMTP_USERNAME and SMTP_PASSWORD must be configured together.")
        if self.smtp_username and self.smtp_security == "none":
            raise ValueError("Authenticated SMTP requires starttls or ssl.")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
