import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NOT_FOUND, AppError
from app.modules.events.models import Event, EventStatus, PaidSalesStatus
from app.modules.history import service as history
from app.modules.notifications import service as notifications
from app.modules.notifications.models import NotificationChannel, NotificationType
from app.modules.orders import service as orders
from app.modules.orders.models import Order, OrderItem, OrderStatus
from app.modules.payments.models import Payment, PaymentPurpose, PaymentStatus
from app.modules.users.models import User

PROVIDER = "biletflow_sim"


async def ensure_payable(session: AsyncSession, event: Event, order: Order) -> None:
    if await orders.expire_locked(session, order, orders.now_utc()):
        await session.commit()
        raise AppError("ORDER_EXPIRED", "Order expired; start a new checkout.", 409)
    if order.status == OrderStatus.EXPIRED:
        raise AppError("ORDER_EXPIRED", "Order expired; start a new checkout.", 409)
    if event.is_suspended:
        raise AppError("EVENT_SUSPENDED", "This event is suspended.", 409)
    if order.status not in orders.PAYABLE_STATUSES or order.total_amount <= 0:
        raise AppError("ORDER_NOT_PAYABLE", "This order is not payable.", 409)
    if (
        event.deleted_at is not None
        or event.status != EventStatus.PUBLISHED
        or event.ends_at <= orders.now_utc()
    ):
        raise AppError("EVENT_NOT_ACCEPTING_PAYMENTS", "This event is not accepting payments.", 409)
    has_paid_type = await session.scalar(
        select(OrderItem.id)
        .where(OrderItem.order_id == order.id, OrderItem.unit_price_amount > 0)
        .limit(1)
    )
    if has_paid_type and event.paid_sales_status != PaidSalesStatus.ACTIVE:
        raise AppError("PAID_SALES_INACTIVE", "Paid sales are not active for this event.", 409)


async def pay(session: AsyncSession, user: User, order_id: uuid.UUID) -> Payment:
    locked = await orders.lock_order(session, order_id, user_id=user.id)
    assert locked is not None
    event, order = locked
    await ensure_payable(session, event, order)
    initiated = await session.scalar(
        select(Payment)
        .where(
            Payment.order_id == order.id,
            Payment.purpose == PaymentPurpose.TICKET_PURCHASE,
            Payment.status == PaymentStatus.INITIATED,
        )
        .with_for_update()
    )
    if initiated is not None:
        await session.commit()
        return initiated
    payment = Payment(
        order_id=order.id,
        purpose=PaymentPurpose.TICKET_PURCHASE,
        provider=PROVIDER,
        provider_payment_ref="sim_" + uuid.uuid4().hex,
        amount=order.total_amount,
    )
    session.add(payment)
    order.status = OrderStatus.AWAITING_PAYMENT
    await orders.audit(session, order, "order.payment_initiated")
    await session.commit()
    return payment


async def simulate(
    session: AsyncSession, user: User, payment_id: uuid.UUID, outcome: str
) -> Payment:
    purpose = await session.scalar(select(Payment.purpose).where(Payment.id == payment_id))
    if purpose == PaymentPurpose.ACTIVATION_FEE:
        from app.modules.activation import service as activation

        return await activation.simulate(session, user, payment_id, outcome)
    order_id = await session.scalar(
        select(Payment.order_id)
        .join(Order, Order.id == Payment.order_id)
        .where(
            Payment.id == payment_id,
            Order.buyer_user_id == user.id,
            Payment.purpose == PaymentPurpose.TICKET_PURCHASE,
        )
    )
    if order_id is None:
        raise AppError(NOT_FOUND, "Payment not found.", 404)
    locked = await orders.lock_order(session, order_id, user_id=user.id)
    assert locked is not None
    event, order = locked
    payment = await session.scalar(
        select(Payment)
        .where(Payment.id == payment_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if payment is None or payment.provider != PROVIDER or not payment.is_simulated:
        raise AppError("PAYMENT_NOT_SIMULATED", "Only demo ticket payments can be simulated.", 409)
    target = PaymentStatus.SUCCEEDED if outcome == "success" else PaymentStatus.FAILED
    if payment.status in (PaymentStatus.SUCCEEDED, PaymentStatus.FAILED):
        if payment.status != target:
            raise AppError(
                "PAYMENT_ALREADY_PROCESSED", "A final payment outcome cannot be changed.", 409
            )
        # Even a replay of a failed callback lazily expires its still-payable order.
        await orders.expire_locked(session, order, orders.now_utc())
        await session.commit()
        return payment
    await ensure_payable(session, event, order)
    if payment.status != PaymentStatus.INITIATED:
        raise AppError("PAYMENT_NOT_PENDING", "This payment attempt is no longer pending.", 409)
    if payment.amount != order.total_amount or payment.currency != order.currency:
        raise AppError("PAYMENT_AMOUNT_MISMATCH", "Payment amount does not match the order.", 409)
    payment.status = target
    payment.processed_at = orders.now_utc()
    payment.provider_payload = {"outcome": outcome, "simulated": True}
    if target == PaymentStatus.SUCCEEDED:
        await orders.complete_locked(session, event, order)
    else:
        payment.failure_reason = "Simulated payment failed."
        await notifications.enqueue(
            session,
            user_id=user.id,
            type=NotificationType.PAYMENT_FAILED,
            channel=NotificationChannel.EMAIL,
            template_key=f"payment_failed.{user.locale}",
            related_entity_type="order",
            related_entity_id=str(order.id),
            payload={
                "order_id": str(order.id),
                "order_number": order.order_number,
                "payment_id": str(payment.id),
                "to_email": order.buyer_email,
            },
        )
    await history.record(
        session,
        actor_user_id=user.id,
        actor_role="attendee",
        action_type=f"payment.{target.value}",
        entity_type="payments",
        entity_id=payment.id,
        event_id=order.event_id,
        summary=f"Simulated payment {target.value}",
        metadata={"order_id": str(order.id), "amount": payment.amount, "simulated": True},
    )
    await session.commit()
    return payment
