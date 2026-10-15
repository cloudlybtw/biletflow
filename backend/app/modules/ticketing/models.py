import uuid
from datetime import datetime

from sqlalchemy import BigInteger, Boolean, FetchedValue, ForeignKey, Integer, Text, text
from sqlalchemy.dialects.postgresql import TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class TicketType(Base):
    __tablename__ = "ticket_types"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    event_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("events.id", ondelete="CASCADE")
    )
    name: Mapped[str] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)
    price_amount: Mapped[int] = mapped_column(BigInteger, server_default=text("0"))
    currency: Mapped[str] = mapped_column(Text, server_default=text("'KZT'"))
    quantity_total: Mapped[int] = mapped_column(Integer)
    quantity_reserved: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    quantity_sold: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    min_per_order: Mapped[int] = mapped_column(Integer, server_default=text("1"))
    max_per_order: Mapped[int] = mapped_column(Integer, server_default=text("10"))
    sales_start_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    sales_end_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    is_hidden: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    display_order: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()"), server_onupdate=FetchedValue()
    )
