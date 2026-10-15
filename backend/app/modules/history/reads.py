"""Retained event records with explicit event scope and no lazy mutations."""

from sqlalchemy import func, select

from app.core.errors import NOT_FOUND, AppError
from app.core.reporting import literal_pattern
from app.db.pagination import read_page
from app.modules.checkin.models import CheckInRecord
from app.modules.history.models import AuditLog
from app.modules.history.schemas import ManagedOrderDetail
from app.modules.orders.models import Attendee, Order, OrderItem
from app.modules.orders.schemas import AttendeeOut, OrderItemOut
from app.modules.payments.models import Payment
from app.modules.payments.schemas import PaymentOut
from app.modules.refunds.models import Refund
from app.modules.ticketing.models import TicketType
from app.modules.tickets.models import Ticket
from app.modules.users.models import User


def range_query(query, column, filters):
    if filters.date_from:
        query = query.where(column >= filters.date_from)
    if filters.date_to:
        query = query.where(column < filters.date_to)
    return query


def public_summary(log: AuditLog) -> str:
    """Project only known business fields; never return raw audit metadata."""
    before, after = log.metadata_.get("before"), log.metadata_.get("after")
    if (
        log.action_type == "ticket_type.updated"
        and isinstance(before, dict)
        and isinstance(after, dict)
    ):
        details = []
        for field, label in [("price_amount", "price (KZT)"), ("quantity_total", "capacity")]:
            old, new = before.get(field), after.get(field)
            if type(old) is int and type(new) is int and old != new:
                details.append(f"{label}: {old} -> {new}")
        if details:
            return "Ticket type updated: " + "; ".join(details)
    if log.action_type == "support.status_changed":
        labels = {
            "open": "Open",
            "in_progress": "In progress",
            "waiting_for_customer": "Waiting for customer",
            "resolved": "Resolved",
        }
        if (
            isinstance(before, str)
            and isinstance(after, str)
            and before in labels
            and after in labels
        ):
            return f"Support case status changed: {labels[before]} -> {labels[after]}"
    return log.summary


async def timeline(session, event_id, filters, page, action_type):
    query = (
        select(AuditLog, User.full_name)
        .outerjoin(User, User.id == AuditLog.actor_user_id)
        .where(AuditLog.event_id == event_id)
    )
    query = range_query(query, AuditLog.occurred_at, filters)
    if action_type:
        query = query.where(AuditLog.action_type == action_type)
    total = await session.scalar(select(func.count()).select_from(query.subquery()))
    rows = (
        await session.execute(
            query.order_by(AuditLog.occurred_at, AuditLog.id).limit(page.limit).offset(page.offset)
        )
    ).all()
    return [
        dict(
            id=log.id,
            occurred_at=log.occurred_at,
            actor_user_id=log.actor_user_id,
            actor_name=name,
            actor_role=log.actor_role,
            action_type=log.action_type,
            entity_type=log.entity_type,
            entity_id=log.entity_id,
            summary=public_summary(log),
        )
        for log, name in rows
    ], total or 0


def orders_query(event_id, filters, status=None, q=None):
    query = range_query(select(Order).where(Order.event_id == event_id), Order.placed_at, filters)
    if status:
        query = query.where(Order.status == status)
    if filters.ticket_type_id:
        query = query.where(
            select(OrderItem.id)
            .where(
                OrderItem.order_id == Order.id, OrderItem.ticket_type_id == filters.ticket_type_id
            )
            .exists()
        )
    if q:
        query = query.where(Order.order_number.ilike(literal_pattern(q), escape="\\"))
    return query.order_by(Order.placed_at.desc().nulls_last(), Order.id)


async def orders(session, event_id, filters, page, status=None, q=None):
    return await read_page(session, orders_query(event_id, filters, status, q), page)


async def order_detail(session, event_id, order_id):
    order = await session.scalar(
        select(Order).where(Order.id == order_id, Order.event_id == event_id)
    )
    if order is None:
        raise AppError(NOT_FOUND, "Order not found.", 404)
    items = list(
        (
            await session.scalars(
                select(OrderItem).where(OrderItem.order_id == order.id).order_by(OrderItem.id)
            )
        ).all()
    )
    attendees = list(
        (
            await session.scalars(
                select(Attendee)
                .where(Attendee.order_item_id.in_([i.id for i in items]))
                .order_by(Attendee.id)
            )
        ).all()
    )
    payments = list(
        (
            await session.scalars(
                select(Payment)
                .where(Payment.order_id == order.id)
                .order_by(Payment.created_at, Payment.id)
            )
        ).all()
    )
    tickets = list(
        (
            await session.scalars(
                select(Ticket.id)
                .where(Ticket.order_item_id.in_([i.id for i in items]))
                .order_by(Ticket.id)
            )
        ).all()
    )
    result = ManagedOrderDetail.model_validate(
        {
            **{column.key: getattr(order, column.key) for column in Order.__mapper__.columns},
            "items": [
                OrderItemOut.model_validate(i).model_copy(
                    update={
                        "attendees": [
                            AttendeeOut.model_validate(a)
                            for a in attendees
                            if a.order_item_id == i.id
                        ]
                    }
                )
                for i in items
            ],
            "payments": [PaymentOut.model_validate(p) for p in payments],
            "ticket_ids": tickets,
        }
    )
    return result


def tickets_query(event_id, filters, status=None):
    query = (
        select(Ticket, Order.id, Attendee, TicketType.name)
        .join(OrderItem, OrderItem.id == Ticket.order_item_id)
        .join(Order, Order.id == OrderItem.order_id)
        .join(Attendee, Attendee.id == Ticket.attendee_id)
        .join(TicketType, TicketType.id == Ticket.ticket_type_id)
        .where(Ticket.event_id == event_id)
    )
    query = range_query(query, Order.placed_at, filters)
    if filters.ticket_type_id:
        query = query.where(Ticket.ticket_type_id == filters.ticket_type_id)
    if status:
        query = query.where(Ticket.status == status)
    return query


def ticket_output(row):
    ticket, order_id, attendee, name = row
    fields = [
        "id",
        "ticket_code",
        "ticket_type_id",
        "attendee_id",
        "status",
        "seat_section_label",
        "seat_row_label",
        "seat_number_label",
        "issued_at",
        "checked_in_at",
        "invalidated_at",
    ]
    return {
        **{key: getattr(ticket, key) for key in fields},
        "order_id": order_id,
        "attendee_name": attendee.full_name,
        "attendee_email": attendee.email,
        "ticket_type_name": name,
    }


async def tickets(session, event_id, filters, page, status=None):
    query = tickets_query(event_id, filters, status)
    total = await session.scalar(select(func.count()).select_from(query.subquery()))
    rows = (
        await session.execute(
            query.order_by(Ticket.issued_at, Ticket.id).limit(page.limit).offset(page.offset)
        )
    ).all()
    return [ticket_output(row) for row in rows], total or 0


async def ticket_detail(session, event_id, ticket_id, filters):
    row = (
        await session.execute(tickets_query(event_id, filters).where(Ticket.id == ticket_id))
    ).one_or_none()
    if row is None:
        raise AppError(NOT_FOUND, "Ticket not found.", 404)
    return ticket_output(row)


async def refunds(session, event_id, filters, page, status=None):
    query = range_query(
        select(Refund).join(Order, Order.id == Refund.order_id).where(Order.event_id == event_id),
        Order.placed_at,
        filters,
    )
    if status:
        query = query.where(Refund.status == status)
    if filters.ticket_type_id:
        query = query.where(
            select(OrderItem.id)
            .where(
                OrderItem.order_id == Order.id, OrderItem.ticket_type_id == filters.ticket_type_id
            )
            .exists()
        )
    return await read_page(session, query.order_by(Refund.created_at, Refund.id), page)


async def checkins(session, event_id, filters, page, result=None):
    query = range_query(
        select(CheckInRecord).where(CheckInRecord.event_id == event_id),
        CheckInRecord.scanned_at,
        filters,
    )
    if result:
        query = query.where(CheckInRecord.result == result)
    if filters.ticket_type_id:
        query = query.join(Ticket, Ticket.id == CheckInRecord.ticket_id).where(
            Ticket.ticket_type_id == filters.ticket_type_id, Ticket.event_id == event_id
        )
    return await read_page(
        session, query.order_by(CheckInRecord.scanned_at, CheckInRecord.id), page
    )
