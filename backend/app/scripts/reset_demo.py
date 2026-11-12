"""Explicit reset of a dedicated *_demo database; never targets the normal DB."""

import argparse
import asyncio
from pathlib import Path

import asyncpg
from sqlalchemy.engine import make_url

from app.core.config import get_settings
from app.db.session import AsyncSessionLocal, engine
from app.scripts.seed_demo import seed


def validate_target(database_url: str, confirmation: str) -> str:
    name = make_url(database_url).database or ""
    if not name.endswith("_demo") or confirmation != name:
        raise ValueError(
            "Reset requires a dedicated database ending in _demo and --confirm matching its exact name."
        )
    return name


MIGRATIONS = Path(__file__).resolve().parents[2] / "migrations"


async def reset(confirmation: str) -> None:
    settings = get_settings()
    name = validate_target(settings.database_url, confirmation)
    conn = await asyncpg.connect(
        settings.database_url.replace("postgresql+asyncpg://", "postgresql://", 1)
    )
    try:
        await conn.execute("DROP SCHEMA public CASCADE; CREATE SCHEMA public;")
        migrations = sorted(MIGRATIONS.glob("*.up.sql"))
        for migration in migrations:
            await conn.execute(migration.read_text())
        # Keep golang-migrate's version marker consistent with the rebuilt schema.
        latest = int(migrations[-1].name.split("_", 1)[0])
        await conn.execute(
            "CREATE TABLE schema_migrations (version bigint PRIMARY KEY, dirty boolean NOT NULL)"
        )
        await conn.execute(
            "INSERT INTO schema_migrations(version, dirty) VALUES($1, false)", latest
        )
    finally:
        await conn.close()
    try:
        async with AsyncSessionLocal() as session:
            await seed(session)
    finally:
        await engine.dispose()
    print(f"Reset and seeded dedicated demo database {name}.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--confirm", required=True, help="Exact dedicated database name, ending in _demo"
    )
    asyncio.run(reset(parser.parse_args().confirm))
