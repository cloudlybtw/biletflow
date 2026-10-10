from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any
from uuid import UUID as UUIDType

from sqlalchemy import FetchedValue, ForeignKey, Text, select, text
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP, UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from app.core.errors import AppError
from app.db.base import Base


class PlatformSetting(Base):
    __tablename__ = "platform_settings"

    key: Mapped[str] = mapped_column(Text, primary_key=True)
    value: Mapped[Any] = mapped_column(JSONB, nullable=False)
    updated_by: Mapped[UUIDType | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()"), server_onupdate=FetchedValue()
    )


async def checkout_settings(session: AsyncSession) -> tuple[int, Decimal]:
    values = dict(
        (
            await session.execute(
                select(PlatformSetting.key, PlatformSetting.value).where(
                    PlatformSetting.key.in_(["order_hold_minutes", "processing_fee_percent"])
                )
            )
        ).all()
    )
    try:
        if any(isinstance(value, bool) for value in values.values()):
            raise ValueError
        hold = Decimal(str(values["order_hold_minutes"]))
        fee = Decimal(str(values["processing_fee_percent"]))
        if (
            not hold.is_finite()
            or not fee.is_finite()
            or hold != hold.to_integral_value()
            or not 1 <= hold <= 10080
            or not 0 <= fee <= 100
        ):
            raise ValueError
        return int(hold), fee
    except (KeyError, ValueError, InvalidOperation) as exc:
        raise AppError(
            "INVALID_CHECKOUT_SETTINGS", "Checkout settings must be configured correctly.", 503
        ) from exc


async def activation_fee(session: AsyncSession) -> int:
    value = await session.scalar(
        select(PlatformSetting.value).where(PlatformSetting.key == "activation_fee_kzt")
    )
    try:
        if isinstance(value, bool):
            raise ValueError
        amount = Decimal(str(value))
        if (
            not amount.is_finite()
            or amount != amount.to_integral_value()
            or not 0 <= amount <= 9_223_372_036_854_775_807
        ):
            raise ValueError
        return int(amount)
    except (ValueError, InvalidOperation) as exc:
        raise AppError(
            "INVALID_ACTIVATION_SETTINGS",
            "Activation fee must be a non-negative whole KZT amount.",
            503,
        ) from exc
