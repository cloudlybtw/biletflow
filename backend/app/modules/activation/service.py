import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.db.settings import activation_fee
from app.modules.activation.models import ActivationStatus, PaidSalesActivation
from app.modules.activation.schemas import ActivationChecklist
from app.modules.events.models import Event, EventStatus, PaidSalesStatus
from app.modules.events.service import get_event
from app.modules.history import service as history
from app.modules.notifications import service as notifications
from app.modules.notifications.models import NotificationChannel, NotificationType
from app.modules.organizers.models import (
    OrganizerProfile,
    PayoutAccount,
    PayoutAccountStatus,
    VerificationStatus,
)
from app.modules.payments.models import Payment, PaymentPurpose, PaymentStatus
from app.modules.payments.service import PROVIDER
from app.modules.ticketing.models import TicketType
from app.modules.users.models import User


def ensure_available(event: Event) -> None:
    if event.is_suspended:
        raise AppError("EVENT_SUSPENDED", "This event is suspended.", 409)
    if event.status == EventStatus.CANCELLED:
        raise AppError("EVENT_CANCELLED", "Cancelled events cannot activate paid sales.", 409)
    if event.ends_at <= datetime.now(UTC):
        raise AppError("EVENT_ENDED", "This event has ended.", 409)
    if event.paid_sales_status == PaidSalesStatus.SUSPENDED:
        raise AppError(
            "PAID_SALES_SUSPENDED", "Only a platform administrator may restore paid sales.", 409
        )


async def get_activation(session: AsyncSession, event: Event) -> PaidSalesActivation | None:
    # Writers lock the event first, matching checkout and moderation's lock order.
    return await session.scalar(
        select(PaidSalesActivation)
        .where(PaidSalesActivation.event_id == event.id)
        .execution_options(populate_existing=True)
    )


async def get_or_create(session: AsyncSession, event: Event) -> PaidSalesActivation:
    activation = await get_activation(session, event)
    if activation is None:
        activation = PaidSalesActivation(
            event_id=event.id,
            organizer_profile_id=event.organizer_profile_id,
            fee_amount=await activation_fee(session),
        )
        session.add(activation)
        await session.flush()
        event.paid_sales_status = PaidSalesStatus.PENDING
    return activation


async def paid_type_exists(session: AsyncSession, event: Event) -> bool:
    return (
        await session.scalar(
            select(TicketType.id)
            .where(
                TicketType.event_id == event.id, TicketType.price_amount > 0, ~TicketType.is_hidden
            )
            .limit(1)
        )
    ) is not None


async def require_paid_type(session: AsyncSession, event: Event) -> None:
    if not await paid_type_exists(session, event):
        raise AppError("NO_PAID_TICKET_TYPE", "Add a visible paid ticket type first.", 409)


async def payout_account(
    session: AsyncSession,
    event: Event,
    activation: PaidSalesActivation | None,
    selected_id=None,
    *,
    lock=False,
) -> PayoutAccount | None:
    account_id = selected_id or (activation.payout_account_id if activation else None)
    query = select(PayoutAccount).where(
        PayoutAccount.organizer_profile_id == event.organizer_profile_id,
        PayoutAccount.status == PayoutAccountStatus.ACTIVE,
        PayoutAccount.currency == "KZT",
        PayoutAccount.is_simulated,
    )
    if account_id:
        query = query.where(PayoutAccount.id == account_id)
    query = query.order_by(
        PayoutAccount.is_default.desc(), PayoutAccount.created_at, PayoutAccount.id
    ).limit(1)
    if lock:
        query = query.with_for_update().execution_options(populate_existing=True)
    return await session.scalar(query)


async def fee_payment(
    session: AsyncSession, activation: PaidSalesActivation | None
) -> Payment | None:
    if activation is None or activation.fee_payment_id is None:
        return None
    return await session.scalar(
        select(Payment)
        .where(Payment.id == activation.fee_payment_id)
        .execution_options(populate_existing=True)
    )


def fee_is_paid(activation: PaidSalesActivation | None, payment: Payment | None) -> bool:
    return bool(
        activation
        and payment
        and payment.activation_id == activation.id
        and payment.purpose == PaymentPurpose.ACTIVATION_FEE
        and payment.status == PaymentStatus.SUCCEEDED
        and payment.amount == activation.fee_amount
        and payment.currency == "KZT"
        and payment.is_simulated
        and payment.provider == PROVIDER
    )


async def checklist(
    session: AsyncSession, event: Event, activation: PaidSalesActivation | None = None
) -> ActivationChecklist:
    activation = activation or await get_activation(session, event)
    profile = await session.get(OrganizerProfile, event.organizer_profile_id)
    account = await payout_account(session, event, activation)
    payment = await fee_payment(session, activation)
    has_type = await paid_type_exists(session, event)
    verified = profile.verification_status == VerificationStatus.VERIFIED
    paid = fee_is_paid(activation, payment)
    accepted = bool(activation and activation.terms_accepted_at)
    return ActivationChecklist(
        event_id=event.id,
        activation_id=activation.id if activation else None,
        status=activation.status if activation else None,
        paid_sales_status=event.paid_sales_status,
        has_paid_ticket_type=has_type,
        identity_verified=verified,
        payout_account_active=account is not None,
        payout_account_id=account.id if account else None,
        fee_paid=paid,
        fee_amount=activation.fee_amount if activation else await activation_fee(session),
        fee_payment_id=activation.fee_payment_id if activation else None,
        terms_accepted=accepted,
        terms_accepted_at=activation.terms_accepted_at if activation else None,
        activated_at=activation.activated_at if activation else None,
        suspended_at=activation.suspended_at if activation else None,
        suspension_reason=activation.suspension_reason if activation else None,
        event_suspended=event.is_suspended,
        ready_to_activate=bool(
            has_type
            and verified
            and account
            and paid
            and accepted
            and not event.is_suspended
            and event.paid_sales_status != PaidSalesStatus.SUSPENDED
            and event.status != EventStatus.CANCELLED
            and event.ends_at > datetime.now(UTC)
        ),
    )


async def audit(
    session: AsyncSession,
    event: Event,
    user: User,
    action: str,
    *,
    entity=None,
    metadata=None,
    admin=False,
) -> None:
    await history.record(
        session,
        actor_user_id=user.id,
        actor_role="platform_admin" if admin else "organizer",
        action_type=action,
        entity_type=entity.__tablename__ if entity is not None else "events",
        entity_id=entity.id if entity is not None else event.id,
        event_id=event.id,
        summary=action.replace(".", " "),
        metadata=metadata or {},
    )


async def accept_terms(session: AsyncSession, event_id, user: User) -> ActivationChecklist:
    event = await get_event(session, event_id, lock=True)
    ensure_available(event)
    activation = await get_or_create(session, event)
    if activation.terms_accepted_at is None:
        activation.terms_accepted_at = datetime.now(UTC)
        await audit(session, event, user, "paid_sales.terms_accepted", entity=activation)
    await session.flush()
    result = await checklist(session, event, activation)
    await session.commit()
    return result


async def pay(session: AsyncSession, event_id, user: User) -> Payment:
    event = await get_event(session, event_id, lock=True)
    ensure_available(event)
    await require_paid_type(session, event)
    activation = await get_or_create(session, event)
    payment = await fee_payment(session, activation)
    if payment and payment.status in {PaymentStatus.INITIATED, PaymentStatus.SUCCEEDED}:
        await session.commit()
        return payment
    payment = Payment(
        activation_id=activation.id,
        purpose=PaymentPurpose.ACTIVATION_FEE,
        provider=PROVIDER,
        provider_payment_ref="sim_" + uuid.uuid4().hex,
        amount=activation.fee_amount,
    )
    session.add(payment)
    await session.flush()
    activation.fee_payment_id = payment.id
    await audit(
        session,
        event,
        user,
        "activation_fee.payment_initiated",
        entity=payment,
        metadata={"amount": payment.amount, "simulated": True},
    )
    if payment.amount == 0:
        payment.status = PaymentStatus.SUCCEEDED
        payment.processed_at = datetime.now(UTC)
        payment.provider_payload = {"outcome": "success", "simulated": True, "zero_fee": True}
        await audit(
            session,
            event,
            user,
            "activation_fee.succeeded",
            entity=payment,
            metadata={"amount": 0, "simulated": True},
        )
    await session.commit()
    return payment


async def simulate(session: AsyncSession, user: User, payment_id, outcome: str) -> Payment:
    event_id = await session.scalar(
        select(PaidSalesActivation.event_id)
        .join(Payment, Payment.activation_id == PaidSalesActivation.id)
        .join(OrganizerProfile, OrganizerProfile.id == PaidSalesActivation.organizer_profile_id)
        .where(
            Payment.id == payment_id,
            Payment.purpose == PaymentPurpose.ACTIVATION_FEE,
            OrganizerProfile.user_id == user.id,
        )
    )
    if event_id is None:
        raise AppError("NOT_FOUND", "Payment not found.", 404)
    event = await get_event(session, event_id, lock=True)
    activation = await get_activation(session, event)
    payment = await session.scalar(
        select(Payment)
        .where(Payment.id == payment_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if not payment.is_simulated or payment.provider != PROVIDER:
        raise AppError(
            "PAYMENT_NOT_SIMULATED", "Only demo activation payments can be simulated.", 409
        )
    target = PaymentStatus.SUCCEEDED if outcome == "success" else PaymentStatus.FAILED
    if payment.status in {PaymentStatus.SUCCEEDED, PaymentStatus.FAILED}:
        if payment.status != target:
            raise AppError(
                "PAYMENT_ALREADY_PROCESSED", "A final payment outcome cannot be changed.", 409
            )
        await session.commit()
        return payment
    ensure_available(event)
    if payment.status != PaymentStatus.INITIATED or activation.fee_payment_id != payment.id:
        raise AppError("PAYMENT_NOT_PENDING", "This activation payment is no longer pending.", 409)
    if payment.amount != activation.fee_amount or payment.currency != activation.currency:
        raise AppError(
            "PAYMENT_AMOUNT_MISMATCH", "Payment amount does not match the activation fee.", 409
        )
    payment.status = target
    payment.processed_at = datetime.now(UTC)
    payment.provider_payload = {"outcome": outcome, "simulated": True}
    if target == PaymentStatus.FAILED:
        payment.failure_reason = "Simulated activation payment failed."
        await notifications.enqueue(
            session,
            user_id=user.id,
            type=NotificationType.PAYMENT_FAILED,
            channel=NotificationChannel.EMAIL,
            template_key=f"activation_payment_failed.{user.locale}",
            related_entity_type="paid_sales_activation",
            related_entity_id=str(activation.id),
            payload={
                "activation_id": str(activation.id),
                "event_id": str(event.id),
                "payment_id": str(payment.id),
                "to_email": user.email,
                "amount": payment.amount,
                "currency": payment.currency,
                "simulated": True,
            },
        )
    await audit(
        session,
        event,
        user,
        f"activation_fee.{target.value}",
        entity=payment,
        metadata={"amount": payment.amount, "simulated": True},
    )
    await session.commit()
    return payment


async def verify_requirements(
    session: AsyncSession, event: Event, activation: PaidSalesActivation, selected_id=None
) -> None:
    profile = await session.scalar(
        select(OrganizerProfile)
        .where(OrganizerProfile.id == event.organizer_profile_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    account = await payout_account(session, event, activation, selected_id, lock=True)
    missing = []
    if not await paid_type_exists(session, event):
        missing.append("has_paid_ticket_type")
    if profile.verification_status != VerificationStatus.VERIFIED:
        missing.append("identity_verified")
    if account is None:
        missing.append("payout_account_active")
    if not fee_is_paid(activation, await fee_payment(session, activation)):
        missing.append("fee_paid")
    if activation.terms_accepted_at is None:
        missing.append("terms_accepted")
    if missing:
        raise AppError(
            "ACTIVATION_CHECKLIST_INCOMPLETE",
            "Complete the paid-sales activation checklist.",
            409,
            {"missing": missing},
        )
    activation.identity_verified_at = (
        activation.identity_verified_at or profile.verified_at or datetime.now(UTC)
    )
    activation.payout_account_id = account.id


async def activate(
    session: AsyncSession, event_id, user: User, selected_id=None
) -> ActivationChecklist:
    event = await get_event(session, event_id, lock=True)
    ensure_available(event)
    activation = await get_activation(session, event)
    if activation is None:
        raise AppError(
            "ACTIVATION_CHECKLIST_INCOMPLETE", "Accept terms and pay the activation fee first.", 409
        )
    if (
        activation.activated_at is not None
        and selected_id
        and selected_id != activation.payout_account_id
    ):
        raise AppError(
            "ACTIVATION_PAYOUT_LOCKED",
            "The activated event's payout account cannot be changed.",
            409,
        )
    await verify_requirements(session, event, activation, selected_id)
    if activation.status != ActivationStatus.ACTIVE:
        activation.status = ActivationStatus.ACTIVE
        activation.activated_at = activation.activated_at or datetime.now(UTC)
        event.paid_sales_status = PaidSalesStatus.ACTIVE
        await audit(
            session,
            event,
            user,
            "paid_sales.activated",
            entity=activation,
            metadata={"simulated": True, "fee_amount": activation.fee_amount},
        )
    await session.flush()
    result = await checklist(session, event, activation)
    await session.commit()
    return result
