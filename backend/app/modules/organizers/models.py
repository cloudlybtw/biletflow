import enum
import uuid
from datetime import datetime

from sqlalchemy import CHAR, Boolean, FetchedValue, ForeignKey, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import CITEXT, TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, pg_enum


class VerificationStatus(enum.StrEnum):
    UNVERIFIED = "unverified"
    PENDING = "pending"
    VERIFIED = "verified"
    REJECTED = "rejected"


class PayoutAccountStatus(enum.StrEnum):
    PENDING = "pending"
    ACTIVE = "active"
    DISABLED = "disabled"


class OrganizerProfile(Base):
    __tablename__ = "organizer_profiles"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), unique=True
    )
    display_name: Mapped[str] = mapped_column(Text)
    contact_email: Mapped[str] = mapped_column(CITEXT)
    contact_phone: Mapped[str | None] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)
    verification_status: Mapped[VerificationStatus] = mapped_column(
        pg_enum(VerificationStatus, "verification_status"), server_default=text("'unverified'")
    )
    verified_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()"), server_onupdate=FetchedValue()
    )


class PayoutAccount(Base):
    __tablename__ = "payout_accounts"
    __table_args__ = (UniqueConstraint("provider", "external_account_ref"),)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    organizer_profile_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizer_profiles.id", ondelete="CASCADE")
    )
    provider: Mapped[str] = mapped_column(Text)
    external_account_ref: Mapped[str] = mapped_column(Text)
    account_holder_name: Mapped[str] = mapped_column(Text)
    currency: Mapped[str] = mapped_column(CHAR(3), server_default=text("'KZT'"))
    status: Mapped[PayoutAccountStatus] = mapped_column(
        pg_enum(PayoutAccountStatus, "payout_account_status"), server_default=text("'pending'")
    )
    is_default: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    is_simulated: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()"), server_onupdate=FetchedValue()
    )
