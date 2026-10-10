import enum
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, Boolean, FetchedValue, ForeignKey, Text, text
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, pg_enum


class PaymentPurpose(enum.StrEnum):
    TICKET_PURCHASE = "ticket_purchase"
    ACTIVATION_FEE = "activation_fee"


class PaymentStatus(enum.StrEnum):
    INITIATED = "initiated"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    order_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("orders.id", ondelete="RESTRICT")
    )
    activation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("paid_sales_activations.id", ondelete="RESTRICT")
    )
    purpose: Mapped[PaymentPurpose] = mapped_column(pg_enum(PaymentPurpose, "payment_purpose"))
    provider: Mapped[str] = mapped_column(Text)
    provider_payment_ref: Mapped[str | None] = mapped_column(Text)
    status: Mapped[PaymentStatus] = mapped_column(
        pg_enum(PaymentStatus, "payment_status"), server_default=text("'initiated'")
    )
    amount: Mapped[int] = mapped_column(BigInteger)
    currency: Mapped[str] = mapped_column(Text, server_default=text("'KZT'"))
    is_simulated: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))
    failure_reason: Mapped[str | None] = mapped_column(Text)
    provider_payload: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    processed_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()"), server_onupdate=FetchedValue()
    )
