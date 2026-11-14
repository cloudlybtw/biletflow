import secrets
import uuid
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import optional_current_user, require_verified
from app.core.errors import AppError
from app.core.pagination import Page, Pagination, pagination
from app.db.session import get_session
from app.db.settings import PlatformSetting
from app.modules.events.models import SeatingMode
from app.modules.events.service import get_event, visible_event
from app.modules.orders.checkout import ensure_sales_open
from app.modules.orders.service import expire_event_locked, now_utc
from app.modules.ticketing.holds import SeatHold, SeatHoldStatus
from app.modules.ticketing.models import TicketType
from app.modules.ticketing.seat_config import SeatBlock, SeatPrice, validate_seat_types
from app.modules.tickets.models import Ticket, TicketStatus
from app.modules.users.models import User
from app.modules.venues.models import Seat, VenueRow, VenueSection

router = APIRouter(tags=["assigned seating"])


class HoldCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ticket_type_id: uuid.UUID
    seat_ids: list[uuid.UUID] = Field(min_length=1, max_length=100)

    @model_validator(mode="after")
    def distinct(self):
        if len(set(self.seat_ids)) != len(self.seat_ids):
            raise ValueError("Each seat can be held only once.")
        return self


class HoldOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    seat_id: uuid.UUID
    ticket_type_id: uuid.UUID
    expires_at: datetime
    status: SeatHoldStatus


class SeatOut(BaseModel):
    id: uuid.UUID
    section: str
    row: str
    number: str
    accessible: bool
    x: float
    y: float
    status: str
    price_category_id: uuid.UUID | None
    ticket_type_id: uuid.UUID | None
    price_amount: int | None
    category_name: str | None
    held_by_me: bool


def venue_seats(event):
    return (
        select(Seat, VenueRow.label, VenueSection.name)
        .join(VenueRow, VenueRow.id == Seat.row_id)
        .join(VenueSection, VenueSection.id == VenueRow.section_id)
        .where(VenueSection.venue_id == event.venue_id)
        .order_by(VenueSection.display_order, VenueRow.display_order, Seat.position_x, Seat.id)
    )


@router.get("/events/{event_id}/seats", response_model=Page[SeatOut])
async def seat_map(
    event_id: uuid.UUID,
    user: User | None = Depends(optional_current_user),
    page: Pagination = Depends(pagination),
    session: AsyncSession = Depends(get_session),
):
    event, _ = await visible_event(session, event_id, user)
    if event.seating_mode != SeatingMode.ASSIGNED:
        raise AppError("SEATING_NOT_ASSIGNED", "This event uses general admission.", 409)
    rows = (await session.execute(venue_seats(event))).all()
    sold = set(
        (
            await session.scalars(
                select(Ticket.seat_id).where(
                    Ticket.event_id == event.id,
                    Ticket.status.in_([TicketStatus.VALID, TicketStatus.CHECKED_IN]),
                )
            )
        ).all()
    )
    holds = {
        hold.seat_id: hold
        for hold in (
            await session.scalars(
                select(SeatHold).where(
                    SeatHold.event_id == event.id,
                    SeatHold.status == SeatHoldStatus.ACTIVE,
                    SeatHold.expires_at > now_utc(),
                )
            )
        ).all()
    }
    from app.modules.venues.models import PriceCategory

    categories = {
        c.id: c.name
        for c in (
            await session.scalars(
                select(PriceCategory).where(PriceCategory.venue_id == event.venue_id)
            )
        ).all()
    }
    mapping = dict(
        (
            await session.execute(
                select(SeatPrice.price_category_id, TicketType)
                .join(TicketType, TicketType.id == SeatPrice.ticket_type_id)
                .where(SeatPrice.event_id == event.id, TicketType.event_id == event.id)
            )
        ).all()
    )
    blocked = set(
        (
            await session.scalars(select(SeatBlock.seat_id).where(SeatBlock.event_id == event.id))
        ).all()
    )

    def configured(seat):
        ticket = mapping.get(seat.price_category_id)
        return (
            ticket
            and not ticket.is_hidden
            and ticket.quantity_total > ticket.quantity_sold + ticket.quantity_reserved
            and (not ticket.sales_start_at or ticket.sales_start_at <= now_utc())
            and (not ticket.sales_end_at or ticket.sales_end_at > now_utc())
            and (not ticket.price_amount or event.paid_sales_status == "active")
        )

    return Page(
        items=[
            SeatOut(
                id=seat.id,
                section=section,
                row=row,
                number=seat.seat_number,
                accessible=seat.is_accessible,
                x=float(seat.position_x),
                y=float(seat.position_y),
                status="sold"
                if seat.id in sold
                else "held"
                if seat.id in holds
                else "unavailable"
                if seat.id in blocked or not configured(seat)
                else "available",
                price_category_id=seat.price_category_id,
                ticket_type_id=mapping[seat.price_category_id].id
                if seat.price_category_id in mapping
                else None,
                price_amount=mapping[seat.price_category_id].price_amount
                if seat.price_category_id in mapping
                else None,
                category_name=categories.get(seat.price_category_id),
                held_by_me=bool(
                    user and seat.id in holds and holds[seat.id].held_by_user_id == user.id
                ),
            )
            for seat, row, section in rows[page.offset : page.offset + page.limit]
        ],
        total=len(rows),
    )


@router.post("/events/{event_id}/seat-holds", response_model=list[HoldOut], status_code=201)
async def create_holds(
    event_id: uuid.UUID,
    data: HoldCreate,
    user: User = Depends(require_verified),
    session: AsyncSession = Depends(get_session),
):
    await visible_event(session, event_id, user)
    event = await get_event(session, event_id, lock=True)
    now = now_utc()
    await expire_event_locked(session, event.id, now)
    ensure_sales_open(event, now)
    if event.seating_mode != SeatingMode.ASSIGNED:
        raise AppError("SEATING_NOT_ASSIGNED", "This event uses general admission.", 409)
    await session.execute(
        update(SeatHold)
        .where(
            SeatHold.event_id == event.id,
            SeatHold.status == SeatHoldStatus.ACTIVE,
            SeatHold.order_id.is_(None),
            SeatHold.expires_at <= now,
        )
        .values(status=SeatHoldStatus.EXPIRED)
    )
    ticket = await session.scalar(
        select(TicketType)
        .where(TicketType.id == data.ticket_type_id, TicketType.event_id == event.id)
        .with_for_update()
    )
    if ticket is None or ticket.is_hidden:
        raise AppError("TICKET_TYPE_UNAVAILABLE", "Choose an available ticket type.", 409)
    if (ticket.sales_start_at and ticket.sales_start_at > now) or (
        ticket.sales_end_at and ticket.sales_end_at <= now
    ):
        raise AppError("TICKET_SALES_CLOSED", "Ticket sales are closed.", 409)
    if ticket.price_amount and event.paid_sales_status != "active":
        raise AppError("PAID_SALES_INACTIVE", "Paid ticket sales are not active.", 409)
    seats = (await session.execute(venue_seats(event).where(Seat.id.in_(data.seat_ids)))).all()
    from types import SimpleNamespace

    await validate_seat_types(
        session,
        event.id,
        [SimpleNamespace(seat_id=seat.id, ticket_type_id=ticket.id) for seat, _, _ in seats],
    )
    if len(seats) != len(data.seat_ids):
        raise AppError("INVALID_SEAT", "Selected seats must belong to this event's venue.", 422)
    held = await session.scalar(
        select(SeatHold.id).where(
            SeatHold.event_id == event.id,
            SeatHold.seat_id.in_(data.seat_ids),
            SeatHold.status == SeatHoldStatus.ACTIVE,
        )
    )
    sold = await session.scalar(
        select(Ticket.id).where(
            Ticket.event_id == event.id,
            Ticket.seat_id.in_(data.seat_ids),
            Ticket.status.in_([TicketStatus.VALID, TicketStatus.CHECKED_IN]),
        )
    )
    if held or sold:
        raise AppError("SEAT_UNAVAILABLE", "A selected seat is no longer available.", 409)
    active = await session.scalar(
        select(func.count())
        .select_from(SeatHold)
        .where(
            SeatHold.event_id == event.id,
            SeatHold.ticket_type_id == ticket.id,
            SeatHold.status == SeatHoldStatus.ACTIVE,
            SeatHold.order_id.is_(None),
        )
    )
    owned = await session.scalar(
        select(func.count())
        .select_from(SeatHold)
        .where(
            SeatHold.event_id == event.id,
            SeatHold.ticket_type_id == ticket.id,
            SeatHold.held_by_user_id == user.id,
            SeatHold.status == SeatHoldStatus.ACTIVE,
            SeatHold.order_id.is_(None),
        )
    )
    if owned + len(seats) > ticket.max_per_order:
        raise AppError(
            "ORDER_LIMIT_EXCEEDED", "Release existing holds before selecting more seats.", 409
        )
    if (
        active + len(seats)
        > ticket.quantity_total - ticket.quantity_sold - ticket.quantity_reserved
    ):
        raise AppError("SOLD_OUT", "No more seats are available for this ticket type.", 409)
    minutes = await session.scalar(
        select(PlatformSetting.value).where(PlatformSetting.key == "seat_hold_minutes")
    )
    if isinstance(minutes, bool) or not isinstance(minutes, int) or not 1 <= minutes <= 10080:
        raise AppError("INVALID_CHECKOUT_SETTINGS", "Invalid seat hold duration.", 503)
    holds = [
        SeatHold(
            event_id=event.id,
            seat_id=seat.id,
            ticket_type_id=ticket.id,
            held_by_user_id=user.id,
            session_token=secrets.token_urlsafe(32),
            expires_at=now + timedelta(minutes=minutes),
        )
        for seat, _, _ in seats
    ]
    session.add_all(holds)
    await session.flush()
    result = [HoldOut.model_validate(hold) for hold in holds]
    await session.commit()
    return result


@router.get("/events/{event_id}/seat-holds", response_model=Page[HoldOut])
async def my_holds(
    event_id: uuid.UUID,
    user: User = Depends(require_verified),
    page: Pagination = Depends(pagination),
    session: AsyncSession = Depends(get_session),
):
    await visible_event(session, event_id, user)
    statement = (
        select(SeatHold)
        .where(
            SeatHold.event_id == event_id,
            SeatHold.held_by_user_id == user.id,
            SeatHold.status == SeatHoldStatus.ACTIVE,
            SeatHold.order_id.is_(None),
            SeatHold.expires_at > now_utc(),
        )
        .order_by(SeatHold.created_at)
    )
    total = await session.scalar(select(func.count()).select_from(statement.subquery()))
    items = (await session.scalars(statement.limit(page.limit).offset(page.offset))).all()
    return Page(items=items, total=total)


@router.delete("/events/{event_id}/seat-holds/{hold_id}", status_code=204)
async def release(
    event_id: uuid.UUID,
    hold_id: uuid.UUID,
    user: User = Depends(require_verified),
    session: AsyncSession = Depends(get_session),
) -> Response:
    await get_event(session, event_id, lock=True)
    hold = await session.scalar(
        select(SeatHold)
        .where(
            SeatHold.id == hold_id,
            SeatHold.event_id == event_id,
            SeatHold.held_by_user_id == user.id,
        )
        .with_for_update()
    )
    if hold is None:
        raise AppError("NOT_FOUND", "Seat hold not found.", 404)
    if hold.order_id is not None:
        raise AppError(
            "HOLD_ATTACHED",
            "This hold is attached to an order and cannot be released separately.",
            409,
        )
    if hold.status == SeatHoldStatus.ACTIVE:
        hold.status = SeatHoldStatus.RELEASED
    await session.commit()
    return Response(status_code=204)
