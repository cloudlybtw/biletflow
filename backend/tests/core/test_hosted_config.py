import ssl

import pytest
from pydantic import ValidationError

from app.core.config import Settings
from app.db.connection import connection_options


def test_provider_urls_keep_credentials_encoded_and_remove_libpq_sslmode():
    url, options = connection_options(
        "postgres://user:p%40ss@database.example/db?sslmode=verify-full", "verify-full"
    )
    assert url.drivername == "postgresql+asyncpg"
    assert url.password == "p@ss" and "sslmode" not in url.query
    assert options["ssl"].verify_mode == ssl.CERT_REQUIRED
    assert options["ssl"].check_hostname
    assert "p@ss" not in str(url)


def test_local_database_uses_explicit_no_tls():
    _, options = connection_options("postgresql+asyncpg://localhost/db")
    assert options == {"ssl": False}


@pytest.mark.parametrize(
    "url,mode",
    [
        ("mysql://localhost/db", "disable"),
        ("postgres://localhost/db?sslmode=disable", "verify-full"),
        ("postgres://localhost/db?ssl=true", "verify-full"),
    ],
)
def test_ambiguous_or_insecure_provider_options_are_rejected(url, mode):
    with pytest.raises(ValueError):
        connection_options(url, mode)


def production(**overrides):
    return Settings(
        _env_file=None,
        **{
            "environment": "production",
            "database_ssl_mode": "verify-full",
            "jwt_secret": "a-unique-test-key-with-at-least-32-characters",
            "web_base_url": "https://web.example.test",
            "cors_origins": ["https://web.example.test"],
            "smtp_security": "starttls",
            **overrides,
        },
    )


def test_hosted_configuration_requires_https_tls_and_unique_secret():
    assert production().environment == "production"
    for fields in [
        {"jwt_secret": "change-me-in-dev-at-least-32-bytes-long"},
        {"database_ssl_mode": "disable"},
        {"web_base_url": "http://web.example.test"},
        {"cors_origins": ["*"]},
        {"cors_origins": ["https://web.example.test/path"]},
        {"smtp_security": "none"},
    ]:
        with pytest.raises(ValidationError):
            production(**fields)


def test_release_migration_uses_same_tls_policy_and_no_shell():
    from app.scripts.migrate import migration_command

    settings = production(database_url="postgres://user:p%40ss@database.example/db")
    args = migration_command(settings, "/usr/local/bin/migrate")
    assert args[-1] == "up" and args[0] == "/usr/local/bin/migrate"
    assert "sslmode=verify-full" in args[-2]
    assert args[-2].startswith("postgresql://")
    assert ";" not in args[-2] and args[1] == "-path"
