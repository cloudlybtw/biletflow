import enum
import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, FetchedValue, ForeignKey, Text, text
from sqlalchemy.dialects.postgresql import CITEXT, TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, pg_enum


class PlatformRole(enum.StrEnum):
    ATTENDEE = "attendee"
    PLATFORM_ADMIN = "platform_admin"


class UserStatus(enum.StrEnum):
    ACTIVE = "active"
    SUSPENDED = "suspended"
    DELETED = "deleted"


class StaffRole(enum.StrEnum):
    EVENT_ADMIN = "event_admin"
    SUPPORT_AGENT = "support_agent"
    CO_ORGANIZER = "co_organizer"


class User(Base):
    __tablename__ = "users"
    __table_args__ = (CheckConstraint("locale IN ('kk', 'ru', 'en')", name="users_locale_check"),)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    email: Mapped[str] = mapped_column(CITEXT, unique=True)
    password_hash: Mapped[str] = mapped_column(Text)
    full_name: Mapped[str] = mapped_column(Text)
    phone: Mapped[str | None] = mapped_column(Text)
    locale: Mapped[str] = mapped_column(Text, server_default=text("'ru'"))
    platform_role: Mapped[PlatformRole] = mapped_column(
        pg_enum(PlatformRole, "platform_role"), server_default=text("'attendee'")
    )
    status: Mapped[UserStatus] = mapped_column(
        pg_enum(UserStatus, "user_status"), server_default=text("'active'")
    )
    email_verified_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    last_login_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()"), server_onupdate=FetchedValue()
    )


class StaffAssignment(Base):
    __tablename__ = "staff_assignments"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    # FK to events(id) is enforced by the database; the ORM ForeignKey is added
    # once the Event model exists (M2), since it can't resolve an unmapped table.
    event_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE")
    )
    role: Mapped[StaffRole] = mapped_column(pg_enum(StaffRole, "staff_role"))
    assigned_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()")
    )
    revoked_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
