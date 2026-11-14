import uuid
from datetime import datetime

from sqlalchemy import BigInteger, ForeignKey, Text, text
from sqlalchemy.dialects.postgresql import TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class OperationalRecord:
    id: Mapped[uuid.UUID] = mapped_column(
        UUID, primary_key=True, server_default=text("gen_random_uuid()")
    )
    event_id: Mapped[uuid.UUID] = mapped_column(UUID, ForeignKey("events.id"))
    status: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()")
    )


class SimulatedPayout(OperationalRecord, Base):
    __tablename__ = "simulated_payouts"
    organizer_user_id: Mapped[uuid.UUID] = mapped_column(UUID, ForeignKey("users.id"))
    amount: Mapped[int] = mapped_column(BigInteger)
    note: Mapped[str] = mapped_column(Text, default="")


class EventReport(OperationalRecord, Base):
    __tablename__ = "event_reports"
    reporter_user_id: Mapped[uuid.UUID] = mapped_column(UUID, ForeignKey("users.id"))
    reason: Mapped[str] = mapped_column(Text)
    resolution: Mapped[str] = mapped_column(Text, default="")
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(UUID, ForeignKey("users.id"))
