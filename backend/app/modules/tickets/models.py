import enum
import uuid
from datetime import datetime

from sqlalchemy import FetchedValue, ForeignKey, Text, text
from sqlalchemy.dialects.postgresql import TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, pg_enum


class TicketStatus(enum.StrEnum):
    VALID = "valid"
    CHECKED_IN = "checked_in"
    CANCELLED = "cancelled"
    REFUNDED = "refunded"


class Ticket(Base):
    __tablename__ = "tickets"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    ticket_code: Mapped[str] = mapped_column(Text, unique=True)
    qr_token: Mapped[str] = mapped_column(Text, unique=True)
    order_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("order_items.id", ondelete="RESTRICT")
    )
    event_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("events.id", ondelete="RESTRICT")
    )
    ticket_type_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ticket_types.id", ondelete="RESTRICT")
    )
    attendee_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("attendees.id", ondelete="RESTRICT"), unique=True
    )
    seat_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("seats.id", ondelete="RESTRICT")
    )
    seat_section_label: Mapped[str | None] = mapped_column(Text)
    seat_row_label: Mapped[str | None] = mapped_column(Text)
    seat_number_label: Mapped[str | None] = mapped_column(Text)
    status: Mapped[TicketStatus] = mapped_column(
        pg_enum(TicketStatus, "ticket_status"), server_default=text("'valid'")
    )
    issued_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()")
    )
    checked_in_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    invalidated_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    pdf_url: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()"), server_onupdate=FetchedValue()
    )
