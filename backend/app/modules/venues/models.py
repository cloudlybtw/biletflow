import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, FetchedValue, ForeignKey, Integer, Numeric, Text, text
from sqlalchemy.dialects.postgresql import TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Venue(Base):
    __tablename__ = "venues"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    name: Mapped[str] = mapped_column(Text)
    address_line: Mapped[str] = mapped_column(Text)
    city: Mapped[str] = mapped_column(Text)
    country: Mapped[str] = mapped_column(Text, server_default=text("'KZ'"))
    latitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))
    longitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))
    timezone: Mapped[str] = mapped_column(Text, server_default=text("'Asia/Almaty'"))
    is_predefined: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()"), server_onupdate=FetchedValue()
    )


class PriceCategory(Base):
    __tablename__ = "price_categories"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    venue_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("venues.id", ondelete="CASCADE")
    )
    code: Mapped[str] = mapped_column(Text)
    name: Mapped[str] = mapped_column(Text)
    display_color: Mapped[str | None] = mapped_column(Text)


class VenueSection(Base):
    __tablename__ = "venue_sections"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    venue_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("venues.id", ondelete="CASCADE")
    )
    name: Mapped[str] = mapped_column(Text)
    display_order: Mapped[int] = mapped_column(Integer, server_default=text("0"))


class VenueRow(Base):
    __tablename__ = "venue_rows"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    section_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("venue_sections.id", ondelete="CASCADE")
    )
    label: Mapped[str] = mapped_column(Text)
    display_order: Mapped[int] = mapped_column(Integer, server_default=text("0"))


class Seat(Base):
    __tablename__ = "seats"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    row_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("venue_rows.id", ondelete="CASCADE")
    )
    price_category_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("price_categories.id", ondelete="SET NULL")
    )
    seat_number: Mapped[str] = mapped_column(Text)
    is_accessible: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    position_x: Mapped[Decimal] = mapped_column(Numeric(8, 2))
    position_y: Mapped[Decimal] = mapped_column(Numeric(8, 2))
