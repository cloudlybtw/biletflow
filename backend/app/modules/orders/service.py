"""Order lifecycle. Mutations lock event → order → campaign → inventory → holds.

The event lock also serializes administration with purchases. Callers commit the
whole transition: counters, payments, tickets, claims, notifications and audit.
"""

import secrets
import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NOT_FOUND, AppError
from app.core.pagination import Pagination
from app.modules.campaigns.models import Campaign
from app.modules.events.models import Event
from app.modules.history import service as history
from app.modules.notifications import service as notifications
from app.modules.notifications.models import NotificationChannel, NotificationType
from app.modules.orders.models import Attendee, Order, OrderItem, OrderStatus, PromoRedemption
from app.modules.orders.schemas import AttendeeOut, OrderDetail, OrderItemOut, OrderOut
from app.modules.payments.models import Payment, PaymentStatus
from app.modules.payments.schemas import PaymentOut
from app.modules.ticketing.holds import SeatHold, SeatHoldStatus
from app.modules.ticketing.models import TicketType
from app.modules.tickets.models import Ticket
from app.modules.users.models import User
from app.modules.venues.models import Seat, VenueRow, VenueSection

PAYABLE_STATUSES = (OrderStatus.PENDING, OrderStatus.AWAITING_PAYMENT)
CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def now_utc() -> datetime:
    return datetime.now(UTC)


async def lock_order(
    session: AsyncSession,
    order_id: uuid.UUID,
    *,
    user_id: uuid.UUID | None = None,
    skip_busy: bool = False,
) -> tuple[Event, Order] | None:
    where = [Order.id == order_id]
    if user_id is not None:
        where.append(Order.buyer_user_id == user_id)
    event_id = await session.scalar(select(Order.event_id).where(*where))
    if event_id is None:
        raise AppError(NOT_FOUND, "Order not found.", 404)
    event = await session.scalar(
        select(Event)
        .where(Event.id == event_id)
        .with_for_update(skip_locked=skip_busy)
        .execution_options(populate_existing=True)
    )
    if event is None and skip_busy:
        return None
    order = await session.scalar(
        select(Order).where(*where).with_for_update().execution_options(populate_existing=True)
    )
    if event is None or order is None:
        raise AppError(NOT_FOUND, "Order not found.", 404)
    return event, order


async def audit(session: AsyncSession, order: Order, action: str) -> None:
    await history.record(
        session,
        actor_user_id=order.buyer_user_id,
        actor_role="attendee",
        action_type=action,
        entity_type="orders",
        entity_id=order.id,
        event_id=order.event_id,
        summary=action.replace(".", " "),
        metadata={
            "order_number": order.order_number,
            "total_amount": order.total_amount,
            "simulated": True,
        },
    )


async def inventory(
    session: AsyncSession, order: Order
) -> tuple[list[OrderItem], list[TicketType], dict[uuid.UUID, int]]:
    items = list(
        (
            await session.scalars(
                select(OrderItem).where(OrderItem.order_id == order.id).order_by(OrderItem.id)
            )
        ).all()
    )
    quantities: dict[uuid.UUID, int] = {}
    for item in items:
        quantities[item.ticket_type_id] = quantities.get(item.ticket_type_id, 0) + item.quantity
    types = list(
        (
            await session.scalars(
                select(TicketType)
                .where(TicketType.id.in_(quantities))
                .order_by(TicketType.id)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
        ).all()
    )
    if len(types) != len(quantities) or any(
        ticket.quantity_reserved < quantities[ticket.id] for ticket in types
    ):
        raise AppError(
            "RESERVATION_STATE_INVALID", "Order inventory reservation is inconsistent.", 409
        )
    return items, types, quantities


async def claimed_campaign(session: AsyncSession, order: Order) -> Campaign | None:
    if order.campaign_id is None or order.discount_amount == 0:
        return None
    campaign = await session.scalar(
        select(Campaign)
        .where(Campaign.id == order.campaign_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if campaign is None or campaign.redemption_count < 1:
        raise AppError(
            "RESERVATION_STATE_INVALID", "Order promotion reservation is inconsistent.", 409
        )
    return campaign


async def expire_locked(session: AsyncSession, order: Order, now: datetime) -> bool:
    if order.status not in PAYABLE_STATUSES or order.expires_at is None or order.expires_at > now:
        return False
    campaign = await claimed_campaign(session, order)
    _, types, quantities = await inventory(session, order)
    for ticket in types:
        ticket.quantity_reserved -= quantities[ticket.id]
    if campaign is not None:
        campaign.redemption_count -= 1
    await session.execute(
        update(SeatHold)
        .where(SeatHold.order_id == order.id, SeatHold.status == SeatHoldStatus.ACTIVE)
        .values(status=SeatHoldStatus.EXPIRED)
    )
    await session.execute(
        update(Payment)
        .where(Payment.order_id == order.id, Payment.status == PaymentStatus.INITIATED)
        .values(
            status=PaymentStatus.CANCELLED,
            processed_at=now,
            failure_reason="Order expired before payment completed.",
        )
    )
    order.status = OrderStatus.EXPIRED
    await audit(session, order, "order.expired")
    return True


async def expire_event_locked(session: AsyncSession, event_id: uuid.UUID, now: datetime) -> int:
    """Lazy cleanup before checkout; the caller already owns the event lock."""
    orders = list(
        (
            await session.scalars(
                select(Order)
                .where(
                    Order.event_id == event_id,
                    Order.status.in_(PAYABLE_STATUSES),
                    Order.expires_at <= now,
                )
                .order_by(Order.id)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
        ).all()
    )
    count = 0
    for order in orders:
        count += await expire_locked(session, order, now)
    return count


async def complete_locked(session: AsyncSession, event: Event, order: Order) -> None:
    if order.status == OrderStatus.COMPLETED:
        return
    if order.status not in PAYABLE_STATUSES:
        raise AppError("ORDER_NOT_PAYABLE", "This order cannot be completed.", 409)
    campaign = await claimed_campaign(session, order)
    items, types, quantities = await inventory(session, order)
    attendees = list(
        (
            await session.scalars(
                select(Attendee)
                .where(Attendee.order_item_id.in_([item.id for item in items]))
                .order_by(Attendee.id)
            )
        ).all()
    )
    by_item: dict[uuid.UUID, list[Attendee]] = {}
    for attendee in attendees:
        by_item.setdefault(attendee.order_item_id, []).append(attendee)
    if any(len(by_item.get(item.id, [])) != item.quantity for item in items):
        raise AppError("RESERVATION_STATE_INVALID", "Order attendee data is inconsistent.", 409)
    seat_ids = [item.seat_id for item in items if item.seat_id]
    seat_rows = (
        await session.execute(
            select(Seat.id, Seat.seat_number, VenueRow.label, VenueSection.name)
            .join(VenueRow, VenueRow.id == Seat.row_id)
            .join(VenueSection, VenueSection.id == VenueRow.section_id)
            .where(Seat.id.in_(seat_ids))
        )
    ).all()
    labels = {row.id: (row.seat_number, row.label, row.name) for row in seat_rows}
    issued: list[Ticket] = []
    for item in items:
        for attendee in by_item[item.id]:
            ticket = Ticket(
                id=uuid.uuid4(),
                ticket_code="BF-" + "".join(secrets.choice(CODE_ALPHABET) for _ in range(10)),
                qr_token="bft_" + secrets.token_urlsafe(24),
                order_item_id=item.id,
                event_id=order.event_id,
                ticket_type_id=item.ticket_type_id,
                attendee_id=attendee.id,
                seat_id=item.seat_id,
            )
            if item.seat_id:
                if item.seat_id not in labels:
                    raise AppError("RESERVATION_STATE_INVALID", "Assigned seat is missing.", 409)
                ticket.seat_number_label, ticket.seat_row_label, ticket.seat_section_label = labels[
                    item.seat_id
                ]
            session.add(ticket)
            issued.append(ticket)
    for ticket_type in types:
        ticket_type.quantity_reserved -= quantities[ticket_type.id]
        ticket_type.quantity_sold += quantities[ticket_type.id]
    await session.execute(
        update(SeatHold)
        .where(SeatHold.order_id == order.id, SeatHold.status == SeatHoldStatus.ACTIVE)
        .values(status=SeatHoldStatus.CONVERTED)
    )
    if campaign is not None:
        session.add(
            PromoRedemption(
                promo_code_id=order.promo_code_id,
                campaign_id=campaign.id,
                order_id=order.id,
                user_id=order.buyer_user_id,
                discount_amount=order.discount_amount,
            )
        )
    order.status = OrderStatus.COMPLETED
    buyer = await session.get(User, order.buyer_user_id)
    if buyer is None:
        raise AppError("BUYER_UNAVAILABLE", "Order buyer is unavailable.", 409)
    for kind in (NotificationType.ORDER_CONFIRMATION, NotificationType.TICKET_DELIVERY):
        await notifications.enqueue(
            session,
            user_id=buyer.id,
            type=kind,
            channel=NotificationChannel.EMAIL,
            template_key=f"{kind.value}.{buyer.locale}",
            related_entity_type="order",
            related_entity_id=str(order.id),
            payload={
                "order_id": str(order.id),
                "order_number": order.order_number,
                "event_title": event.title,
                "total_amount": order.total_amount,
                "currency": order.currency,
                "ticket_ids": [str(ticket.id) for ticket in issued],
                "to_email": order.buyer_email,
                "full_name": order.buyer_name,
            },
        )
    await audit(session, order, "order.completed")


async def detail(session: AsyncSession, user: User, order_id: uuid.UUID) -> OrderDetail:
    locked = await lock_order(session, order_id, user_id=user.id)
    assert locked is not None
    _, order = locked
    await expire_locked(session, order, now_utc())
    await session.commit()
    items = list(
        (
            await session.scalars(
                select(OrderItem).where(OrderItem.order_id == order.id).order_by(OrderItem.id)
            )
        ).all()
    )
    attendees = (
        await session.scalars(
            select(Attendee)
            .where(Attendee.order_item_id.in_([item.id for item in items]))
            .order_by(Attendee.id)
        )
    ).all()
    payments = (
        await session.scalars(
            select(Payment)
            .where(Payment.order_id == order.id)
            .order_by(Payment.created_at, Payment.id)
        )
    ).all()
    ticket_ids = list(
        (
            await session.scalars(
                select(Ticket.id)
                .join(OrderItem, OrderItem.id == Ticket.order_item_id)
                .where(OrderItem.order_id == order.id)
                .order_by(Ticket.id)
            )
        ).all()
    )
    return OrderDetail(
        **OrderOut.model_validate(order).model_dump(),
        items=[
            OrderItemOut.model_validate(item).model_copy(
                update={
                    "attendees": [
                        AttendeeOut.model_validate(attendee)
                        for attendee in attendees
                        if attendee.order_item_id == item.id
                    ]
                }
            )
            for item in items
        ],
        payments=[PaymentOut.model_validate(payment) for payment in payments],
        ticket_ids=ticket_ids,
    )


async def my_orders(
    session: AsyncSession, user: User, page: Pagination
) -> tuple[list[OrderOut], int]:
    expired_ids = list(
        (
            await session.scalars(
                select(Order.id)
                .where(
                    Order.buyer_user_id == user.id,
                    Order.status.in_(PAYABLE_STATUSES),
                    Order.expires_at <= now_utc(),
                )
                .order_by(Order.expires_at, Order.id)
                .limit(100)
            )
        ).all()
    )
    await session.commit()
    for order_id in expired_ids:
        locked = await lock_order(session, order_id, user_id=user.id)
        assert locked is not None
        await expire_locked(session, locked[1], now_utc())
        await session.commit()
    where = Order.buyer_user_id == user.id
    total = await session.scalar(select(func.count()).select_from(Order).where(where))
    orders = (
        await session.scalars(
            select(Order)
            .where(where)
            .order_by(Order.created_at.desc(), Order.id)
            .limit(page.limit)
            .offset(page.offset)
        )
    ).all()
    return [OrderOut.model_validate(order) for order in orders], total or 0


async def sweep_expired(session: AsyncSession, *, batch_size: int = 100) -> int:
    ids = list(
        (
            await session.scalars(
                select(Order.id)
                .where(Order.status.in_(PAYABLE_STATUSES), Order.expires_at <= now_utc())
                .order_by(Order.expires_at, Order.id)
                .limit(batch_size)
            )
        ).all()
    )
    await session.commit()
    count = 0
    for order_id in ids:
        locked = await lock_order(session, order_id, skip_busy=True)
        if locked is not None:
            count += await expire_locked(session, locked[1], now_utc())
        await session.commit()
    return count
