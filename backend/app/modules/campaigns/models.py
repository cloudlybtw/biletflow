import enum
import uuid
from datetime import datetime

from sqlalchemy import BigInteger, Boolean, FetchedValue, ForeignKey, Integer, Text, text
from sqlalchemy.dialects.postgresql import CITEXT, TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, pg_enum


class DiscountType(enum.StrEnum):
    PERCENT = "percent"
    FIXED = "fixed"


class CampaignStatus(enum.StrEnum):
    DRAFT = "draft"
    ACTIVE = "active"
    DISABLED = "disabled"
    EXPIRED = "expired"


class Campaign(Base):
    __tablename__ = "campaigns"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    event_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("events.id", ondelete="CASCADE")
    )
    name: Mapped[str] = mapped_column(Text)
    discount_type: Mapped[DiscountType] = mapped_column(
        pg_enum(DiscountType, "discount_type"), server_default=text("'percent'")
    )
    discount_value: Mapped[int] = mapped_column(BigInteger)
    currency: Mapped[str] = mapped_column(Text, server_default=text("'KZT'"))
    starts_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    ends_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    max_redemptions: Mapped[int | None] = mapped_column(Integer)
    redemption_count: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    status: Mapped[CampaignStatus] = mapped_column(
        pg_enum(CampaignStatus, "campaign_status"), server_default=text("'draft'")
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()"), server_onupdate=FetchedValue()
    )


class PromoCode(Base):
    __tablename__ = "promo_codes"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    campaign_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("campaigns.id", ondelete="CASCADE")
    )
    code: Mapped[str] = mapped_column(CITEXT, unique=True)
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()")
    )


class CampaignQR(Base):
    __tablename__ = "campaign_qr_codes"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    campaign_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("campaigns.id", ondelete="CASCADE")
    )
    promo_code_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("promo_codes.id", ondelete="CASCADE")
    )
    token: Mapped[str] = mapped_column(Text, unique=True)
    target_url: Mapped[str] = mapped_column(Text)
    image_url: Mapped[str | None] = mapped_column(Text)
    label: Mapped[str | None] = mapped_column(Text)
    scan_count: Mapped[int] = mapped_column(BigInteger, server_default=text("0"))
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()")
    )


class CampaignTicketType(Base):
    __tablename__ = "campaign_ticket_types"

    campaign_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("campaigns.id", ondelete="CASCADE"), primary_key=True
    )
    ticket_type_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ticket_types.id", ondelete="CASCADE"), primary_key=True
    )
