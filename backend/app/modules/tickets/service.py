import io
import uuid

import segno
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NOT_FOUND, AppError
from app.core.pagination import Pagination
from app.modules.events.models import Event
from app.modules.orders.models import Attendee, Order, OrderItem
from app.modules.ticketing.models import TicketType
from app.modules.tickets.models import Ticket
from app.modules.tickets.schemas import TicketEventOut, TicketOut
from app.modules.users.models import User
from app.modules.venues.models import Venue


def ticket_query(user_id: uuid.UUID):
    # Tickets remain visible to the buyer after an event is unpublished/cancelled
    # or an attendee has a different email. No other account may fetch QR tokens.
    return (
        select(
            Ticket,
            Order.id.label("order_id"),
            Attendee,
            TicketType.name.label("ticket_type_name"),
            Event,
            Venue,
        )
        .join(OrderItem, OrderItem.id == Ticket.order_item_id)
        .join(Order, Order.id == OrderItem.order_id)
        .join(Attendee, Attendee.id == Ticket.attendee_id)
        .join(TicketType, TicketType.id == Ticket.ticket_type_id)
        .join(Event, Event.id == Ticket.event_id)
        .outerjoin(Venue, Venue.id == Event.venue_id)
        .where(Order.buyer_user_id == user_id)
    )


def output(row) -> TicketOut:
    ticket, order_id, attendee, type_name, event, venue = row
    return TicketOut(
        id=ticket.id,
        order_id=order_id,
        ticket_code=ticket.ticket_code,
        qr_token=ticket.qr_token,
        qr_image_url=f"/api/v1/tickets/{ticket.id}/qr.png",
        pdf_url=f"/api/v1/tickets/{ticket.id}/pdf",
        ticket_type_id=ticket.ticket_type_id,
        ticket_type_name=type_name,
        attendee_id=attendee.id,
        attendee_name=attendee.full_name,
        attendee_email=attendee.email,
        status=ticket.status,
        seat_id=ticket.seat_id,
        seat_section_label=ticket.seat_section_label,
        seat_row_label=ticket.seat_row_label,
        seat_number_label=ticket.seat_number_label,
        issued_at=ticket.issued_at,
        checked_in_at=ticket.checked_in_at,
        invalidated_at=ticket.invalidated_at,
        event=TicketEventOut(
            id=event.id,
            title=event.title,
            starts_at=event.starts_at,
            ends_at=event.ends_at,
            timezone=event.timezone,
            venue_name=venue.name if venue else None,
            venue_address=venue.address_line if venue else None,
            venue_city=venue.city if venue else None,
        ),
    )


async def detail(session: AsyncSession, user: User, ticket_id: uuid.UUID) -> TicketOut:
    row = (await session.execute(ticket_query(user.id).where(Ticket.id == ticket_id))).one_or_none()
    if row is None:
        raise AppError(NOT_FOUND, "Ticket not found.", 404)
    return output(row)


async def my_tickets(
    session: AsyncSession, user: User, page: Pagination
) -> tuple[list[TicketOut], int]:
    query = ticket_query(user.id)
    total = await session.scalar(select(func.count()).select_from(query.subquery()))
    rows = (
        await session.execute(
            query.order_by(Ticket.issued_at.desc(), Ticket.id).limit(page.limit).offset(page.offset)
        )
    ).all()
    return [output(row) for row in rows], total or 0


def qr_png(token: str) -> bytes:
    result = io.BytesIO()
    segno.make(token, error="h", micro=False).save(
        result, kind="png", scale=8, border=4, dark="#000000", light="#ffffff"
    )
    return result.getvalue()
