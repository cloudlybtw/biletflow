import uuid

from fastapi.encoders import jsonable_encoder
from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import EventAccess
from app.core.errors import NOT_FOUND, VALIDATION_ERROR, AppError
from app.modules.events.service import audit, editable, get_event
from app.modules.ticketing.models import TicketType
from app.modules.ticketing.schemas import TicketTypeCreate, TicketTypeUpdate


async def save(
    session: AsyncSession,
    access: EventAccess,
    data: TicketTypeCreate | TicketTypeUpdate,
    ticket_id: uuid.UUID | None = None,
) -> TicketType:
    # All inventory administration serializes on the event, and each changed ticket
    # is locked too so future checkout reservations cannot race quantity reductions.
    event = await get_event(session, access.event_id, lock=True)
    editable(event)
    changes = data.model_dump(exclude_unset=True)
    if ticket_id:
        ticket = await session.scalar(
            select(TicketType)
            .where(TicketType.id == ticket_id, TicketType.event_id == event.id)
            .with_for_update()
        )
        if ticket is None:
            raise AppError(NOT_FOUND, "Ticket type not found.", 404)
        try:
            merged = TicketTypeCreate.model_validate(
                {
                    **TicketTypeCreate.model_validate(ticket, from_attributes=True).model_dump(),
                    **changes,
                }
            )
        except ValidationError as exc:
            raise AppError(
                VALIDATION_ERROR,
                "Invalid ticket fields.",
                422,
                {"errors": jsonable_encoder(exc.errors())},
            ) from exc
        if merged.quantity_total < ticket.quantity_reserved + ticket.quantity_sold:
            raise AppError(
                "QUANTITY_BELOW_COMMITTED", "Quantity cannot fall below reserved + sold.", 409
            )
        before = {key: getattr(ticket, key) for key in changes}
    else:
        merged = data
        ticket = TicketType(event_id=event.id, **merged.model_dump())
        before = {}
    query = select(func.coalesce(func.sum(TicketType.quantity_total), 0)).where(
        TicketType.event_id == event.id
    )
    if ticket_id:
        query = query.where(TicketType.id != ticket_id)
    allocated = await session.scalar(query)
    if event.capacity is not None and allocated + merged.quantity_total > event.capacity:
        raise AppError("CAPACITY_EXCEEDED", "Ticket inventory exceeds event capacity.", 409)
    for field, value in merged.model_dump().items():
        setattr(ticket, field, value)
    try:
        session.add(ticket)
        await session.flush()
    except IntegrityError as exc:
        await session.rollback()
        raise AppError(
            "TICKET_TYPE_NAME_TAKEN", "A ticket type with this name already exists.", 409
        ) from exc
    await audit(
        session,
        access,
        "ticket_type.updated" if ticket_id else "ticket_type.created",
        ticket,
        {"before": before, "after": changes},
    )
    await session.commit()
    return ticket
