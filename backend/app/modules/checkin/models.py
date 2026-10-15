import enum
import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, Text, text
from sqlalchemy.dialects.postgresql import TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, pg_enum


class CheckInAction(enum.StrEnum):
    CHECK_IN = "check_in"
    REVERSE = "reverse"


class CheckInResult(enum.StrEnum):
    VALID = "valid"
    DUPLICATE = "duplicate"
    CANCELLED = "cancelled"
    REFUNDED = "refunded"
    INVALID = "invalid"
    WRONG_EVENT = "wrong_event"
    CAMPAIGN_CODE_REJECTED = "campaign_code_rejected"


class CheckInSource(enum.StrEnum):
    QR_SCAN = "qr_scan"
    MANUAL_SEARCH = "manual_search"


class CheckInRecord(Base):
    __tablename__ = "check_in_records"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    ticket_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tickets.id", ondelete="SET NULL")
    )
    event_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("events.id", ondelete="CASCADE")
    )
    scanned_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    device_id: Mapped[str | None] = mapped_column(Text)
    action: Mapped[CheckInAction] = mapped_column(pg_enum(CheckInAction, "check_in_action"))
    result: Mapped[CheckInResult] = mapped_column(pg_enum(CheckInResult, "check_in_result"))
    source: Mapped[CheckInSource] = mapped_column(
        pg_enum(CheckInSource, "check_in_source"), server_default=text("'qr_scan'")
    )
    scanned_token: Mapped[str | None] = mapped_column(Text)
    reverses_record_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("check_in_records.id", ondelete="SET NULL")
    )
    notes: Mapped[str | None] = mapped_column(Text)
    scanned_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()")
    )
