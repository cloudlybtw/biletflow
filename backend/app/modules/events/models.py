import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, FetchedValue, ForeignKey, Integer, Text, text
from sqlalchemy.dialects.postgresql import TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, pg_enum


class EventVisibility(enum.StrEnum):
    PUBLIC = "public"
    UNLISTED = "unlisted"
    PRIVATE = "private"


class EventStatus(enum.StrEnum):
    DRAFT = "draft"
    PUBLISHED = "published"
    UNPUBLISHED = "unpublished"
    CANCELLED = "cancelled"


class SeatingMode(enum.StrEnum):
    GENERAL_ADMISSION = "general_admission"
    ASSIGNED = "assigned"


class PaidSalesStatus(enum.StrEnum):
    DISABLED = "disabled"
    PENDING = "pending"
    ACTIVE = "active"
    SUSPENDED = "suspended"


class EventCategory(Base):
    __tablename__ = "event_categories"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    slug: Mapped[str] = mapped_column(Text, unique=True)
    name_kk: Mapped[str] = mapped_column(Text)
    name_ru: Mapped[str] = mapped_column(Text)
    name_en: Mapped[str] = mapped_column(Text)
    display_order: Mapped[int] = mapped_column(Integer, server_default=text("0"))


class Event(Base):
    __tablename__ = "events"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    organizer_profile_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizer_profiles.id", ondelete="RESTRICT")
    )
    venue_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("venues.id", ondelete="RESTRICT")
    )
    category_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("event_categories.id", ondelete="SET NULL")
    )
    title: Mapped[str] = mapped_column(Text)
    slug: Mapped[str] = mapped_column(Text, unique=True)
    description: Mapped[str | None] = mapped_column(Text)
    timezone: Mapped[str] = mapped_column(Text, server_default=text("'Asia/Almaty'"))
    starts_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True))
    ends_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True))
    visibility: Mapped[EventVisibility] = mapped_column(
        pg_enum(EventVisibility, "event_visibility"), server_default=text("'public'")
    )
    status: Mapped[EventStatus] = mapped_column(
        pg_enum(EventStatus, "event_status"), server_default=text("'draft'")
    )
    seating_mode: Mapped[SeatingMode] = mapped_column(
        pg_enum(SeatingMode, "seating_mode"), server_default=text("'general_admission'")
    )
    paid_sales_status: Mapped[PaidSalesStatus] = mapped_column(
        pg_enum(PaidSalesStatus, "paid_sales_status"), server_default=text("'disabled'")
    )
    is_suspended: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    suspended_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    suspended_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    suspension_reason: Mapped[str | None] = mapped_column(Text)
    capacity: Mapped[int | None] = mapped_column(Integer)
    registration_opens_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    registration_closes_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    refund_policy: Mapped[str | None] = mapped_column(Text)
    ics_uid: Mapped[str] = mapped_column(
        Text, unique=True, server_default=text("gen_random_uuid()::text || '@biletflow.kz'")
    )
    ics_sequence: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    published_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    deleted_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    cancelled_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()"), server_onupdate=FetchedValue()
    )


class EventImage(Base):
    __tablename__ = "event_images"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    event_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("events.id", ondelete="CASCADE")
    )
    url: Mapped[str] = mapped_column(Text)
    alt_text: Mapped[str | None] = mapped_column(Text)
    sort_order: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    is_cover: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
