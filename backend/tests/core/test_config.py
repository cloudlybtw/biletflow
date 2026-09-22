from app.core.config import Settings

_ENV_VARS = (
    "DATABASE_URL",
    "JWT_SECRET",
    "JWT_ALGORITHM",
    "ACCESS_TOKEN_EXPIRE_MINUTES",
    "WEB_BASE_URL",
    "SMTP_HOST",
    "SMTP_PORT",
    "SMTP_FROM",
)


def test_settings_uses_dev_defaults_with_no_env(monkeypatch):
    for var in _ENV_VARS:
        monkeypatch.delenv(var, raising=False)

    settings = Settings(_env_file=None)

    assert (
        settings.database_url == "postgresql+asyncpg://biletflow:biletflow@localhost:5432/biletflow"
    )
    assert settings.jwt_algorithm == "HS256"
    assert settings.access_token_expire_minutes == 15
    assert settings.smtp_host == "localhost"
    assert settings.smtp_port == 1025


def test_settings_reads_environment_overrides(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", "super-secret")
    monkeypatch.setenv("SMTP_PORT", "2525")

    settings = Settings(_env_file=None)

    assert settings.jwt_secret == "super-secret"
    assert settings.smtp_port == 2525
