import enum
import uuid
from datetime import datetime

from sqlalchemy import BigInteger, Boolean, FetchedValue, ForeignKey, Text, text
from sqlalchemy.dialects.postgresql import TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, pg_enum


class RefundStatus(enum.StrEnum):
    REQUESTED = "requested"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class Refund(Base):
    __tablename__ = "refunds"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    payment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("payments.id", ondelete="RESTRICT")
    )
    order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("orders.id", ondelete="RESTRICT")
    )
    initiated_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    amount: Mapped[int] = mapped_column(BigInteger)
    currency: Mapped[str] = mapped_column(Text, server_default=text("'KZT'"))
    reason: Mapped[str | None] = mapped_column(Text)
    status: Mapped[RefundStatus] = mapped_column(
        pg_enum(RefundStatus, "refund_status"), server_default=text("'requested'")
    )
    provider_refund_ref: Mapped[str | None] = mapped_column(Text)
    is_simulated: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))
    processed_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()"), server_onupdate=FetchedValue()
    )
