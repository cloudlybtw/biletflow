import contextlib
from collections.abc import AsyncGenerator
from pathlib import Path

import asyncpg
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.db.session import get_session
from app.main import create_app

MIGRATIONS_DIR = Path(__file__).resolve().parents[1] / "migrations"
TEST_DB_NAME = "biletflow_test"

# Tables whose rows are seeded by a migration (not test setup) and should
# survive the per-test truncate so every test sees them by default.
SEED_TABLES = {"platform_settings"}


def _asyncpg_dsn(database_url: str, database: str | None = None) -> str:
    dsn = database_url.replace("postgresql+asyncpg://", "postgresql://", 1)
    if database is not None:
        base, _, _ = dsn.rpartition("/")
        dsn = f"{base}/{database}"
    return dsn


def _test_database_url() -> str:
    base, _, _ = get_settings().database_url.rpartition("/")
    return f"{base}/{TEST_DB_NAME}"


async def _create_test_database() -> None:
    conn = await asyncpg.connect(_asyncpg_dsn(get_settings().database_url))
    try:
        with contextlib.suppress(asyncpg.exceptions.DuplicateDatabaseError):
            await conn.execute(f"CREATE DATABASE {TEST_DB_NAME}")
    finally:
        await conn.close()


async def _apply_migrations() -> None:
    conn = await asyncpg.connect(_asyncpg_dsn(get_settings().database_url, TEST_DB_NAME))
    try:
        await conn.execute("DROP SCHEMA public CASCADE; CREATE SCHEMA public;")
        for migration in sorted(MIGRATIONS_DIR.glob("*.up.sql")):
            await conn.execute(migration.read_text())
    finally:
        await conn.close()


@pytest.fixture(scope="session", autouse=True)
async def _migrated_database() -> None:
    await _create_test_database()
    await _apply_migrations()


@pytest.fixture(scope="session")
async def test_engine(_migrated_database: None) -> AsyncGenerator:
    engine = create_async_engine(_test_database_url(), pool_pre_ping=True)
    yield engine
    await engine.dispose()


@pytest.fixture(scope="session")
def test_sessionmaker(test_engine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(test_engine, expire_on_commit=False, class_=AsyncSession)


@pytest.fixture(autouse=True)
async def _truncate_tables(test_sessionmaker: async_sessionmaker[AsyncSession]) -> None:
    async with test_sessionmaker() as session:
        result = await session.execute(
            text("SELECT tablename FROM pg_tables WHERE schemaname = 'public'")
        )
        tables = [row[0] for row in result.all() if row[0] not in SEED_TABLES]
        if tables:
            table_list = ", ".join(f'"{table}"' for table in tables)
            await session.execute(text(f"TRUNCATE TABLE {table_list} RESTART IDENTITY CASCADE"))
            await session.commit()


@pytest.fixture
async def db_session(
    test_sessionmaker: async_sessionmaker[AsyncSession],
) -> AsyncGenerator[AsyncSession, None]:
    async with test_sessionmaker() as session:
        yield session


@pytest.fixture
async def client(
    test_sessionmaker: async_sessionmaker[AsyncSession],
) -> AsyncGenerator[AsyncClient, None]:
    app = create_app()

    async def _get_test_session() -> AsyncGenerator[AsyncSession, None]:
        async with test_sessionmaker() as session:
            yield session

    app.dependency_overrides[get_session] = _get_test_session

    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
