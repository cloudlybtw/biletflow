import enum

from sqlalchemy import Enum, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

import app.db.models  # noqa: F401  (registers every mapper)
from app.db.base import Base
from app.modules.users.models import PlatformRole, User, UserStatus
from tests.factories import create_organizer, create_user


async def test_mapped_columns_match_database_schema(db_session: AsyncSession):
    rows = await db_session.execute(
        text(
            "SELECT table_name, column_name, is_nullable FROM information_schema.columns "
            "WHERE table_schema = 'public'"
        )
    )
    db_columns = {(r.table_name, r.column_name): r.is_nullable == "YES" for r in rows}

    for table in Base.metadata.tables.values():
        mapped = {column.name for column in table.columns}
        in_db = {name for (tbl, name) in db_columns if tbl == table.name}
        assert mapped == in_db, f"{table.name}: column set differs from the migration"
        for column in table.columns:
            assert column.nullable == db_columns[(table.name, column.name)], (
                f"{table.name}.{column.name}: nullability differs from the migration"
            )


async def test_mapped_enums_match_postgres_enum_labels(db_session: AsyncSession):
    rows = await db_session.execute(
        text(
            "SELECT t.typname, e.enumlabel FROM pg_type t "
            "JOIN pg_enum e ON e.enumtypid = t.oid ORDER BY t.typname, e.enumsortorder"
        )
    )
    pg_labels: dict[str, list[str]] = {}
    for typname, label in rows:
        pg_labels.setdefault(typname, []).append(label)

    for table in Base.metadata.tables.values():
        for column in table.columns:
            if isinstance(column.type, Enum):
                enum_cls: type[enum.Enum] = column.type.enum_class
                assert [m.value for m in enum_cls] == pg_labels[column.type.name], (
                    f"{table.name}.{column.name}: {enum_cls.__name__} labels differ"
                )


async def test_user_insert_reads_back_server_defaults(db_session: AsyncSession):
    user = await create_user(db_session)

    assert user.id is not None
    assert user.locale == "ru"
    assert user.platform_role is PlatformRole.ATTENDEE
    assert user.status is UserStatus.ACTIVE
    assert user.created_at.tzinfo is not None
    assert user.email_verified_at is None


async def test_updated_at_is_set_by_trigger(db_session: AsyncSession):
    user = await create_user(db_session)
    before = user.updated_at
    await db_session.commit()

    # now() is the transaction start time, so the update runs in a new transaction.
    await db_session.execute(update(User).where(User.id == user.id).values(full_name="Renamed"))
    await db_session.commit()
    refreshed = await db_session.scalar(
        select(User).where(User.id == user.id).execution_options(populate_existing=True)
    )
    assert refreshed.updated_at > before


async def test_organizer_factory_links_profile_to_user(db_session: AsyncSession):
    profile = await create_organizer(db_session)

    assert profile.user_id is not None
    assert profile.verification_status == "unverified"
