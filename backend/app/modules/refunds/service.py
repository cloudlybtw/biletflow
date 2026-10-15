"""Full order reversal; event → order → inventory → ticket locks.

Helpers never commit so event cancellation can reuse the same atomic lifecycle.
HTTP entry points commit only after tickets, counters, refund, audit and outbox.
"""

import uuid
from collections import Counter

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import EventAccess
from app.core.errors import (
    NOT_FOUND,
    ORDER_NOT_COMPLETED,
    ORDER_NOT_FREE,
    ORDER_NOT_PAID,
    REFUND_STATE_INVALID,
    AppError,
)
from app.modules.events.models import Event
from app.modules.history import service as history
from app.modules.notifications import service as notifications
from app.modules.notifications.models import NotificationChannel, NotificationType
from app.modules.orders import service as orders
from app.modules.orders.models import Order, OrderItem, OrderStatus
from app.modules.payments.models import Payment, PaymentPurpose, PaymentStatus
from app.modules.refunds.models import Refund, RefundStatus
from app.modules.refunds.schemas import CancellationOut, RefundOut, ReversalIn
from app.modules.ticketing.models import TicketType
from app.modules.tickets.models import Ticket, TicketStatus
from app.modules.users.models import User


def inconsistent() -> AppError:
    return AppError(REFUND_STATE_INVALID, "Order payment or ticket state is inconsistent.", 409)


async def lock_scoped_order(
    session: AsyncSession, access: EventAccess, order_id: uuid.UUID
) -> tuple[Event, Order]:
    exists = await session.scalar(
        select(Order.id).where(Order.id == order_id, Order.event_id == access.event_id)
    )
    if exists is None:
        raise AppError(NOT_FOUND, "Order not found.", 404)
    locked = await orders.lock_order(session, order_id)
    assert locked is not None
    return locked


async def reverse_completed_locked(
    session: AsyncSession,
    access: EventAccess,
    event: Event,
    order: Order,
    reason: str | None,
) -> tuple[list[uuid.UUID], Refund | None]:
    """Caller owns the event and order locks; supports zero-total and paid orders."""
    paid = order.total_amount > 0
    now = orders.now_utc()
    target = OrderStatus.REFUNDED if paid else OrderStatus.CANCELLED
    changed = await session.scalar(
        update(Order)
        .where(Order.id == order.id, Order.status == OrderStatus.COMPLETED)
        .values(status=target)
        .returning(Order.id)
    )
    if changed is None:
        raise AppError(
            ORDER_NOT_COMPLETED, "Only a completed order can be cancelled or refunded.", 409
        )

    refund = None
    if paid:
        payments = list(
            (
                await session.scalars(
                    select(Payment)
                    .where(
                        Payment.order_id == order.id,
                        Payment.purpose == PaymentPurpose.TICKET_PURCHASE,
                        Payment.status == PaymentStatus.SUCCEEDED,
                    )
                    .with_for_update()
                )
            ).all()
        )
        existing_refund = await session.scalar(select(Refund.id).where(Refund.order_id == order.id))
        if len(payments) != 1 or existing_refund is not None:
            raise inconsistent()
        payment = payments[0]
        if (
            not order.is_simulated
            or not payment.is_simulated
            or payment.provider != "biletflow_sim"
            or payment.amount != order.total_amount
            or payment.currency != order.currency
            or order.currency != "KZT"
        ):
            raise inconsistent()
        refund = Refund(
            payment_id=payment.id,
            order_id=order.id,
            initiated_by_user_id=access.user.id,
            amount=payment.amount,
            currency=payment.currency,
            reason=reason,
            status=RefundStatus.COMPLETED,
            provider_refund_ref="sim_refund_" + uuid.uuid4().hex,
            is_simulated=True,
            processed_at=now,
        )
        session.add(refund)

    items = list(
        (await session.scalars(select(OrderItem).where(OrderItem.order_id == order.id))).all()
    )
    items_by_id = {item.id: item for item in items}
    quantities: Counter[uuid.UUID] = Counter()
    for item in items:
        quantities[item.ticket_type_id] += item.quantity
    # Match checkout's inventory-before-ticket order. Admission only locks tickets.
    await session.execute(
        select(TicketType.id)
        .where(TicketType.id.in_(quantities))
        .order_by(TicketType.id)
        .with_for_update()
    )
    tickets = list(
        (
            await session.scalars(
                select(Ticket)
                .where(Ticket.order_item_id.in_([item.id for item in items]))
                .order_by(Ticket.id)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
        ).all()
    )
    if (
        not items
        or Counter(ticket.order_item_id for ticket in tickets)
        != {item.id: item.quantity for item in items}
        or any(
            ticket.status not in (TicketStatus.VALID, TicketStatus.CHECKED_IN)
            or ticket.event_id != event.id
            or ticket.ticket_type_id != items_by_id[ticket.order_item_id].ticket_type_id
            for ticket in tickets
        )
    ):
        raise inconsistent()
    for type_id in sorted(quantities):
        await orders.adjust_inventory(session, type_id, reserved=0, sold=-quantities[type_id])
    await session.execute(
        update(Ticket)
        .where(Ticket.id.in_([ticket.id for ticket in tickets]))
        .values(
            status=TicketStatus.REFUNDED if paid else TicketStatus.CANCELLED, invalidated_at=now
        )
    )
    await session.flush()
    action = "order.refunded" if paid else "order.cancelled"
    metadata = {
        "order_number": order.order_number,
        "amount": order.total_amount,
        "currency": order.currency,
        "reason": reason,
        "simulated": True,
        "ticket_ids": [str(ticket.id) for ticket in tickets],
    }
    await history.record(
        session,
        actor_user_id=access.user.id,
        actor_role=access.actor_role,
        action_type=action,
        entity_type="orders",
        entity_id=order.id,
        event_id=event.id,
        summary="Order fully refunded (simulated)" if paid else "Free registration cancelled",
        metadata=metadata,
    )
    if refund is not None:
        await history.record(
            session,
            actor_user_id=access.user.id,
            actor_role=access.actor_role,
            action_type="refund.completed",
            entity_type="refunds",
            entity_id=refund.id,
            event_id=event.id,
            summary="Full simulated refund completed",
            metadata={**metadata, "order_id": str(order.id), "payment_id": str(refund.payment_id)},
        )
    if order.buyer_user_id is not None:
        buyer = await session.get(User, order.buyer_user_id)
        assert buyer is not None
        kind = NotificationType.REFUND_COMPLETED if paid else NotificationType.EVENT_UPDATE
        await notifications.enqueue(
            session,
            user_id=buyer.id,
            type=kind,
            channel=NotificationChannel.EMAIL,
            template_key=f"{kind.value}.{buyer.locale}",
            related_entity_type="order",
            related_entity_id=str(order.id),
            payload={
                **metadata,
                "order_id": str(order.id),
                "event_id": str(event.id),
                "event_title": event.title,
                "to_email": order.buyer_email,
                "full_name": order.buyer_name,
                "status": target.value,
                "refund_id": str(refund.id) if refund else None,
            },
        )
    return [ticket.id for ticket in tickets], refund


async def cancel_free(
    session: AsyncSession, access: EventAccess, order_id: uuid.UUID, data: ReversalIn
) -> CancellationOut:
    event, order = await lock_scoped_order(session, access, order_id)
    if order.total_amount != 0:
        raise AppError(ORDER_NOT_FREE, "Use a full refund for a paid order.", 409)
    ticket_ids, _ = await reverse_completed_locked(session, access, event, order, data.reason)
    await session.commit()
    return CancellationOut(order_id=order.id, ticket_ids=ticket_ids)


async def refund_paid(
    session: AsyncSession, access: EventAccess, order_id: uuid.UUID, data: ReversalIn
) -> RefundOut:
    event, order = await lock_scoped_order(session, access, order_id)
    if order.total_amount == 0:
        raise AppError(ORDER_NOT_PAID, "Cancel a zero-total registration instead.", 409)
    _, refund = await reverse_completed_locked(session, access, event, order, data.reason)
    assert refund is not None
    result = RefundOut.model_validate(refund)
    await session.commit()
    return result
