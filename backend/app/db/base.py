import enum

from sqlalchemy import Enum
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    # Columns filled by the database (ids, defaults, trigger-set updated_at)
    # are read back via RETURNING on insert/update instead of a lazy refresh.
    __mapper_args__ = {"eager_defaults": True}


def pg_enum(enum_cls: type[enum.Enum], name: str) -> Enum:
    """Map an existing Postgres enum type; values (not member names) are stored."""
    return Enum(
        enum_cls,
        name=name,
        create_type=False,
        values_callable=lambda cls: [member.value for member in cls],
        validate_strings=True,
    )
