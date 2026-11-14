import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import ForeignKey, Text, delete, select
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from app.core.deps import EventAccess, require_event_role
from app.core.errors import AppError
from app.db.base import Base
from app.db.session import get_session
from app.modules.events.service import editable, get_event
from app.modules.history.service import record
from app.modules.ticketing.holds import SeatHold
from app.modules.ticketing.models import TicketType
from app.modules.tickets.models import Ticket
from app.modules.users.models import StaffRole
from app.modules.venues.models import PriceCategory, Seat, VenueRow, VenueSection

router = APIRouter(tags=["seat configuration"])
manager = require_event_role(StaffRole.CO_ORGANIZER)


class SeatPrice(Base):
    __tablename__ = "event_price_category_ticket_types"
    event_id: Mapped[uuid.UUID] = mapped_column(UUID, ForeignKey("events.id"), primary_key=True)
    price_category_id: Mapped[uuid.UUID] = mapped_column(
        UUID, ForeignKey("price_categories.id"), primary_key=True
    )
    ticket_type_id: Mapped[uuid.UUID] = mapped_column(UUID, ForeignKey("ticket_types.id"))


class SeatBlock(Base):
    __tablename__ = "event_seat_blocks"
    event_id: Mapped[uuid.UUID] = mapped_column(UUID, ForeignKey("events.id"), primary_key=True)
    seat_id: Mapped[uuid.UUID] = mapped_column(UUID, ForeignKey("seats.id"), primary_key=True)
    reason: Mapped[str] = mapped_column(Text)


class PriceUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ticket_type_id: uuid.UUID | None


class BlockUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    blocked: bool
    reason: str = Field(min_length=1, max_length=500)


class PriceOut(BaseModel):
    price_category_id: uuid.UUID
    name: str
    ticket_type_id: uuid.UUID | None
    price_amount: int | None


async def prices(session, event):
    rows = (
        await session.execute(
            select(PriceCategory, SeatPrice.ticket_type_id, TicketType.price_amount)
            .outerjoin(
                SeatPrice,
                (SeatPrice.price_category_id == PriceCategory.id)
                & (SeatPrice.event_id == event.id),
            )
            .outerjoin(TicketType, TicketType.id == SeatPrice.ticket_type_id)
            .where(PriceCategory.venue_id == event.venue_id)
            .order_by(PriceCategory.code)
        )
    ).all()
    return [
        PriceOut(price_category_id=c.id, name=c.name, ticket_type_id=t, price_amount=p)
        for c, t, p in rows
    ]


async def busy(session, event_id, seats):
    held = await session.scalar(
        select(SeatHold.id)
        .where(
            SeatHold.event_id == event_id,
            SeatHold.seat_id.in_(seats),
            SeatHold.status == "active",
            SeatHold.expires_at > datetime.now(UTC),
        )
        .limit(1)
    )
    sold = await session.scalar(
        select(Ticket.id)
        .where(
            Ticket.event_id == event_id,
            Ticket.seat_id.in_(seats),
            Ticket.status.in_(["valid", "checked_in"]),
        )
        .limit(1)
    )
    return bool(held or sold)


async def log(session, access, entity_id, action, metadata):
    await record(
        session,
        actor_user_id=access.user.id,
        actor_role=access.actor_role,
        event_id=access.event_id,
        entity_type="seat_configuration",
        entity_id=entity_id,
        action_type=action,
        summary=action.replace(".", " "),
        metadata=metadata,
    )


@router.get("/events/{event_id}/seat-prices", response_model=list[PriceOut])
async def list_prices(
    access: EventAccess = Depends(manager), session: AsyncSession = Depends(get_session)
):
    return await prices(session, await get_event(session, access.event_id))


@router.patch("/events/{event_id}/seat-prices/{category_id}", response_model=list[PriceOut])
async def set_price(
    category_id: uuid.UUID,
    data: PriceUpdate,
    access: EventAccess = Depends(manager),
    session: AsyncSession = Depends(get_session),
):
    event = await get_event(session, access.event_id, lock=True)
    editable(event)
    category = await session.get(PriceCategory, category_id)
    ticket = await session.get(TicketType, data.ticket_type_id) if data.ticket_type_id else None
    if event.seating_mode != "assigned" or not category or category.venue_id != event.venue_id:
        raise AppError("INVALID_PRICE_CATEGORY", "Choose a category from the assigned venue.", 422)
    if data.ticket_type_id and (not ticket or ticket.event_id != event.id or ticket.is_hidden):
        raise AppError("INVALID_TICKET_TYPE", "Choose a visible event ticket type.", 422)
    old = await session.get(SeatPrice, (event.id, category.id))
    if old and old.ticket_type_id == data.ticket_type_id:
        return await prices(session, event)
    if await busy(session, event.id, select(Seat.id).where(Seat.price_category_id == category.id)):
        raise AppError(
            "SEATS_COMMITTED", "Release holds or refund tickets before changing pricing.", 409
        )
    if old:
        await session.delete(old)
        await session.flush()
    if ticket:
        session.add(
            SeatPrice(event_id=event.id, price_category_id=category.id, ticket_type_id=ticket.id)
        )
    await log(
        session,
        access,
        category.id,
        "seat.price_changed",
        {"ticket_type_id": str(data.ticket_type_id) if data.ticket_type_id else None},
    )
    await session.commit()
    return await prices(session, event)


@router.patch("/events/{event_id}/seats/{seat_id}/block", status_code=204)
async def block_seat(
    seat_id: uuid.UUID,
    data: BlockUpdate,
    access: EventAccess = Depends(manager),
    session: AsyncSession = Depends(get_session),
):
    event = await get_event(session, access.event_id, lock=True)
    editable(event)
    valid = await session.scalar(
        select(Seat.id)
        .join(VenueRow, VenueRow.id == Seat.row_id)
        .join(VenueSection, VenueSection.id == VenueRow.section_id)
        .where(Seat.id == seat_id, VenueSection.venue_id == event.venue_id)
    )
    if not valid or event.seating_mode != "assigned":
        raise AppError("NOT_FOUND", "Seat not found.", 404)
    if data.blocked and await busy(session, event.id, [seat_id]):
        raise AppError("SEATS_COMMITTED", "Held or sold seats cannot be blocked.", 409)
    await session.execute(
        delete(SeatBlock).where(SeatBlock.event_id == event.id, SeatBlock.seat_id == seat_id)
    )
    if data.blocked:
        session.add(SeatBlock(event_id=event.id, seat_id=seat_id, reason=data.reason))
    await log(
        session,
        access,
        seat_id,
        "seat.block_changed",
        {"blocked": data.blocked, "reason": data.reason},
    )
    await session.commit()


async def validate_seat_types(session, event_id, holds):
    if not holds:
        return
    mapping = dict(
        (
            await session.execute(
                select(SeatPrice.price_category_id, SeatPrice.ticket_type_id).where(
                    SeatPrice.event_id == event_id
                )
            )
        ).all()
    )
    seats = {
        s.id: s
        for s in (
            await session.scalars(select(Seat).where(Seat.id.in_([h.seat_id for h in holds])))
        ).all()
    }
    blocked = set(
        (
            await session.scalars(select(SeatBlock.seat_id).where(SeatBlock.event_id == event_id))
        ).all()
    )
    if any(
        h.seat_id in blocked
        or h.seat_id not in seats
        or mapping.get(seats[h.seat_id].price_category_id) != h.ticket_type_id
        for h in holds
    ):
        raise AppError(
            "SEAT_PRICE_MISMATCH",
            "Seat is unavailable or its price category does not match the ticket type.",
            409,
        )
