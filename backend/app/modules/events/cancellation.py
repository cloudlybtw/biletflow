"""Atomic event cancellation; caller holds the event's NO KEY UPDATE lock."""

from collections import defaultdict

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import EventAccess
from app.core.errors import EVENT_CANCELLATION_STATE_INVALID, AppError
from app.modules.events.models import Event
from app.modules.notifications import service as notifications
from app.modules.notifications.models import NotificationChannel, NotificationType
from app.modules.orders import service as orders
from app.modules.orders.models import Order, OrderStatus
from app.modules.refunds import service as refunds
from app.modules.ticketing.holds import SeatHold, SeatHoldStatus
from app.modules.tickets.models import Ticket, TicketStatus
from app.modules.users.models import User


async def cascade_locked(
    session: AsyncSession,
    access: EventAccess,
    event: Event,
) -> dict[str, int]:
    event_orders = list(
        (
            await session.scalars(
                select(Order)
                .where(Order.event_id == event.id)
                .order_by(Order.id)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
        ).all()
    )
    counts = {
        "orders_refunded": 0,
        "orders_cancelled": 0,
        "orders_expired": 0,
        "event_notifications_queued": 0,
    }
    by_buyer = defaultdict(list)
    terminal = (OrderStatus.EXPIRED, OrderStatus.CANCELLED, OrderStatus.REFUNDED)
    for order in event_orders:
        if order.status in terminal:
            continue
        if order.status == OrderStatus.COMPLETED:
            _, refund = await refunds.reverse_completed_locked(
                session, access, event, order, "Event cancelled."
            )
            counts["orders_refunded" if refund is not None else "orders_cancelled"] += 1
        elif order.status in orders.PAYABLE_STATUSES:
            await orders.release_pending_locked(
                session, order, event.cancelled_at, cancelled_by=access
            )
            counts["orders_expired"] += 1
        else:
            # PAID must never persist, and partial refunds are outside this MVP.
            raise AppError(
                EVENT_CANCELLATION_STATE_INVALID,
                "An order needs reconciliation before event cancellation.",
                409,
            )
        if order.buyer_user_id is not None:
            by_buyer[order.buyer_user_id].append(order)

    # Terminal orders cannot leave a valid admission behind. Fail atomically if
    # imported/inconsistent history would violate this invariant.
    active_ticket = await session.scalar(
        select(Ticket.id)
        .where(
            Ticket.event_id == event.id,
            Ticket.status.in_((TicketStatus.VALID, TicketStatus.CHECKED_IN)),
        )
        .limit(1)
    )
    if active_ticket is not None:
        raise AppError(
            EVENT_CANCELLATION_STATE_INVALID,
            "Active tickets remain on an order requiring reconciliation.",
            409,
        )

    # Also release unattached/live holds; cancellation is independent of expiry.
    await session.execute(
        update(SeatHold)
        .where(
            SeatHold.event_id == event.id,
            SeatHold.status == SeatHoldStatus.ACTIVE,
        )
        .values(status=SeatHoldStatus.RELEASED)
    )
    for buyer_id, affected in by_buyer.items():
        buyer = await session.get(User, buyer_id)
        assert buyer is not None
        await notifications.enqueue(
            session,
            user_id=buyer.id,
            type=NotificationType.EVENT_CANCELLED,
            channel=NotificationChannel.EMAIL,
            template_key=f"event_cancelled.{buyer.locale}",
            related_entity_type="event",
            related_entity_id=str(event.id),
            payload={
                "event_id": str(event.id),
                "event_title": event.title,
                "event_slug": event.slug,
                "status": "cancelled",
                "cancelled_at": event.cancelled_at.isoformat(),
                "ics_uid": event.ics_uid,
                "ics_sequence": event.ics_sequence,
                "order_ids": [str(order.id) for order in affected],
                "order_numbers": [order.order_number for order in affected],
                "to_email": buyer.email,
                "full_name": buyer.full_name,
                "simulated": True,
            },
        )
        counts["event_notifications_queued"] += 1
    return counts
