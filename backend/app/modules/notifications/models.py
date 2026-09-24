import enum
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import ForeignKey, Text, text
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, pg_enum


class NotificationType(enum.StrEnum):
    ACCOUNT_VERIFICATION = "account_verification"
    ORDER_CONFIRMATION = "order_confirmation"
    PAYMENT_FAILED = "payment_failed"
    TICKET_DELIVERY = "ticket_delivery"
    EVENT_UPDATE = "event_update"
    EVENT_CANCELLED = "event_cancelled"
    REFUND_COMPLETED = "refund_completed"
    PAYOUT_STATUS = "payout_status"
    SUPPORT_NEW_MESSAGE = "support_new_message"
    SUPPORT_ASSIGNED = "support_assigned"
    SUPPORT_STATUS_CHANGED = "support_status_changed"
    PASSWORD_RESET = "password_reset"  # added in migration 0003


class NotificationChannel(enum.StrEnum):
    EMAIL = "email"
    IN_APP = "in_app"


class NotificationStatus(enum.StrEnum):
    QUEUED = "queued"
    SENT = "sent"
    FAILED = "failed"
    READ = "read"


class Notification(Base):
    """Outbox row; the background sender (M7.3) delivers queued email rows."""

    __tablename__ = "notifications"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE")
    )
    type: Mapped[NotificationType] = mapped_column(pg_enum(NotificationType, "notification_type"))
    channel: Mapped[NotificationChannel] = mapped_column(
        pg_enum(NotificationChannel, "notification_channel")
    )
    related_entity_type: Mapped[str | None] = mapped_column(Text)
    related_entity_id: Mapped[str | None] = mapped_column(Text)
    template_key: Mapped[str] = mapped_column(Text)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    status: Mapped[NotificationStatus] = mapped_column(
        pg_enum(NotificationStatus, "notification_status"), server_default=text("'queued'")
    )
    error_message: Mapped[str | None] = mapped_column(Text)
    sent_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    read_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()")
    )
