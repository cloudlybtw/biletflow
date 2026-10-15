import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, FetchedValue, ForeignKey, Text, text
from sqlalchemy.dialects.postgresql import TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, pg_enum


class CaseType(enum.StrEnum):
    ATTENDEE = "attendee"
    ORGANIZER = "organizer"


class Category(enum.StrEnum):
    TICKET_DELIVERY = "ticket_delivery"
    PAYMENT = "payment"
    REFUND = "refund"
    SEATING = "seating"
    EVENT_INFORMATION = "event_information"
    CHECK_IN = "check_in"
    ACCOUNT = "account"
    TECHNICAL = "technical"


class CaseStatus(enum.StrEnum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    WAITING_FOR_CUSTOMER = "waiting_for_customer"
    RESOLVED = "resolved"


class SenderRole(enum.StrEnum):
    REQUESTER = "requester"
    STAFF = "staff"


class SupportCase(Base):
    __tablename__ = "support_cases"
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    case_number: Mapped[str] = mapped_column(Text, unique=True)
    case_type: Mapped[CaseType] = mapped_column(pg_enum(CaseType, "support_case_type"))
    category: Mapped[Category] = mapped_column(pg_enum(Category, "support_category"))
    subject: Mapped[str] = mapped_column(Text)
    opened_by_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT")
    )
    event_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("events.id", ondelete="SET NULL")
    )
    order_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("orders.id", ondelete="SET NULL")
    )
    ticket_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tickets.id", ondelete="SET NULL")
    )
    status: Mapped[CaseStatus] = mapped_column(
        pg_enum(CaseStatus, "support_status"), server_default=text("'open'")
    )
    assigned_to_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    last_message_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    resolved_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()"), server_onupdate=FetchedValue()
    )


class SupportMessage(Base):
    __tablename__ = "support_messages"
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    case_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("support_cases.id", ondelete="CASCADE")
    )
    sender_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT")
    )
    sender_role: Mapped[SenderRole] = mapped_column(pg_enum(SenderRole, "support_sender_role"))
    body: Mapped[str] = mapped_column(Text)
    is_internal_note: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    read_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()")
    )
