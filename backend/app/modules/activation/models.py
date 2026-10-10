import enum
import uuid
from datetime import datetime

from sqlalchemy import CHAR, BigInteger, FetchedValue, ForeignKey, Text, text
from sqlalchemy.dialects.postgresql import TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, pg_enum


class ActivationStatus(enum.StrEnum):
    PENDING = "pending"
    ACTIVE = "active"
    SUSPENDED = "suspended"


class PaidSalesActivation(Base):
    __tablename__ = "paid_sales_activations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    event_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("events.id", ondelete="CASCADE"), unique=True
    )
    organizer_profile_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizer_profiles.id", ondelete="RESTRICT")
    )
    payout_account_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("payout_accounts.id", ondelete="RESTRICT")
    )
    fee_payment_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("payments.id", ondelete="SET NULL")
    )
    fee_amount: Mapped[int] = mapped_column(BigInteger)
    currency: Mapped[str] = mapped_column(CHAR(3), server_default=text("'KZT'"))
    identity_verified_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    terms_accepted_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    status: Mapped[ActivationStatus] = mapped_column(
        pg_enum(ActivationStatus, "activation_status"), server_default=text("'pending'")
    )
    activated_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    suspended_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    suspended_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    suspension_reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()"), server_onupdate=FetchedValue()
    )
