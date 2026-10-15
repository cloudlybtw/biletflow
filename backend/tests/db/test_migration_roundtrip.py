import uuid

import asyncpg

from app.core.config import get_settings
from tests.conftest import MIGRATIONS_DIR, _asyncpg_dsn


async def test_m2_m5_migrations_upgrade_downgrade_upgrade():
    # A separate schema keeps rollback verification away from the API test data.
    schema = "migration_test_" + uuid.uuid4().hex
    connection = await asyncpg.connect(_asyncpg_dsn(get_settings().database_url))
    try:
        await connection.execute(
            f'CREATE SCHEMA "{schema}"; SET search_path TO "{schema}", public;'
        )
        for name in [
            "0001_init_schema",
            "0002_platform_support",
            "0003_password_reset_notification",
        ]:
            await connection.execute((MIGRATIONS_DIR / f"{name}.up.sql").read_text())
        for _ in range(2):
            for name in [
                "0004_event_catalog",
                "0005_campaign_qr_promo_link",
                "0006_checkout_guards",
                "0007_activation_moderation",
            ]:
                await connection.execute((MIGRATIONS_DIR / f"{name}.up.sql").read_text())
            assert await connection.fetchval("SELECT count(*) FROM event_categories") == 4
            assert await connection.fetchval("SELECT count(*) FROM seats") == 20
            columns = await connection.fetch(
                "SELECT table_name, column_name FROM information_schema.columns WHERE table_schema = $1",
                schema,
            )
            pairs = {(row["table_name"], row["column_name"]) for row in columns}
            assert ("events", "deleted_at") in pairs
            assert ("campaign_qr_codes", "promo_code_id") in pairs
            assert ("events", "is_suspended") in pairs
            assert ("payments", "activation_id") in pairs
            indexes = {
                row["indexname"]
                for row in await connection.fetch(
                    "SELECT indexname FROM pg_indexes WHERE schemaname = $1", schema
                )
            }
            assert "uq_tickets_attendee" in indexes
            assert "uq_payments_initiated_ticket_order" in indexes
            assert "uq_payments_live_activation" in indexes
            for name in [
                "0007_activation_moderation",
                "0006_checkout_guards",
                "0005_campaign_qr_promo_link",
                "0004_event_catalog",
            ]:
                await connection.execute((MIGRATIONS_DIR / f"{name}.down.sql").read_text())
            assert await connection.fetchval("SELECT count(*) FROM venues") == 0
            assert await connection.fetchval("SELECT count(*) FROM event_categories") == 0
    finally:
        await connection.execute("ROLLBACK")
        await connection.execute(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')
        await connection.close()
