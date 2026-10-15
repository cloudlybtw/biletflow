import asyncio
import uuid
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from sqlalchemy import func, select, update

from app.modules.campaigns.models import Campaign
from app.modules.checkin import service as checkin
from app.modules.checkin.models import CheckInRecord
from app.modules.events import cancellation
from app.modules.events import service as events
from app.modules.events.models import Event, EventStatus, PaidSalesStatus
from app.modules.history.models import AuditLog
from app.modules.notifications.models import Notification, NotificationType
from app.modules.orders.models import Order, OrderStatus, PromoRedemption
from app.modules.orders.service import sweep_expired
from app.modules.payments.models import Payment
from app.modules.refunds.models import Refund
from app.modules.ticketing.holds import SeatHold
from app.modules.ticketing.models import TicketType
from app.modules.tickets.models import Ticket
from app.modules.users.models import PlatformRole, StaffRole
from app.modules.venues.models import Seat
from tests.factories import (
    auth_headers,
    create_event,
    create_seat_hold,
    create_staff_assignment,
    create_ticket_type,
    create_verified_user,
)
from tests.orders.conftest import add_promo
from tests.orders.helpers import checkout, pay, placed_order, simulate
from tests.orders.test_expiry import make_expired
from tests.refunds.test_refunds import completed, order_tickets, reverse


async def cancel_event(client, context, *, user=None):
    return await client.post(
        f"/api/v1/events/{context.event_id}/cancel", headers=auth_headers(user or context.owner)
    )


async def fresh_order(db_session, order):
    return await db_session.get(Order, uuid.UUID(order["id"]), populate_existing=True)


async def event_notices(db_session):
    return list(
        (
            await db_session.scalars(
                select(Notification).where(Notification.type == NotificationType.EVENT_CANCELLED)
            )
        ).all()
    )


async def assert_event_cancelled(db_session, context, *, sequence=1):
    event = await db_session.get(Event, context.event_id, populate_existing=True)
    assert event.status == "cancelled" and event.cancelled_at is not None
    assert event.paid_sales_status == "disabled" and event.ics_sequence == sequence
    assert (
        await db_session.scalar(
            select(func.count())
            .select_from(Ticket)
            .where(Ticket.event_id == event.id, Ticket.status.in_(["valid", "checked_in"]))
        )
        == 0
    )
    types = (
        await db_session.scalars(
            select(TicketType)
            .where(TicketType.event_id == event.id)
            .execution_options(populate_existing=True)
        )
    ).all()
    assert all(t.quantity_sold == t.quantity_reserved == 0 for t in types)
    return event


async def test_cancellation_atomically_reverses_mixed_orders_and_notifies_each_buyer_once(
    client, db_session, context
):
    campaign, _ = await add_promo(db_session, context, maximum=10)
    paid = await completed(client, db_session, context, promo_code="CHECKOUT15")
    pending = await placed_order(client, context, quantity=3, promo_code="CHECKOUT15")
    initiated = await pay(client, context, pending["id"])
    free_type = await create_ticket_type(db_session, context.event_id, price_amount=0)
    await db_session.execute(
        update(Event).where(Event.id == context.event_id).values(ics_sequence=7)
    )
    await db_session.commit()
    free = await placed_order(
        client,
        context,
        buyer=context.other_buyer,
        data={"items": [{"ticket_type_id": str(free_type.id), "quantity": 2}]},
    )
    ticket = (await order_tickets(db_session, paid))[0]
    original = await db_session.get(Event, context.event_id, populate_existing=True)
    uid = original.ics_uid
    scan = await client.post(
        f"/api/v1/checkin/scan?event_id={context.event_id}",
        json={"token": ticket.qr_token},
        headers=auth_headers(context.owner),
    )
    assert scan.status_code == 201 and scan.json()["result"] == "valid"
    response = await cancel_event(client, context)
    assert response.status_code == 200 and response.json()["status"] == "cancelled", response.text
    event = await assert_event_cancelled(db_session, context, sequence=8)
    assert event.ics_uid == uid
    assert (await fresh_order(db_session, paid)).status == "refunded"
    assert (await fresh_order(db_session, free)).status == "cancelled"
    unpaid = await fresh_order(db_session, pending)
    assert unpaid.status == "expired" and unpaid.expires_at == datetime.fromisoformat(
        pending["expires_at"]
    )
    assert all(t.status == "refunded" for t in await order_tickets(db_session, paid))
    assert all(t.status == "cancelled" for t in await order_tickets(db_session, free))
    assert await order_tickets(db_session, pending) == []
    used = await db_session.get(Ticket, ticket.id, populate_existing=True)
    assert used.checked_in_at is not None and used.invalidated_at is not None
    payment = await db_session.get(Payment, uuid.UUID(initiated["id"]), populate_existing=True)
    assert (
        payment.status == "cancelled"
        and payment.failure_reason == "Event cancelled before payment completed."
    )
    payment_audit = await db_session.scalar(
        select(AuditLog).where(
            AuditLog.action_type == "payment.cancelled", AuditLog.entity_id == initiated["id"]
        )
    )
    assert payment_audit.actor_user_id == context.owner.id
    assert payment_audit.metadata_["reason"] == "event_cancelled"
    refund = await db_session.scalar(select(Refund))
    assert (
        refund.amount == paid["total_amount"]
        and refund.is_simulated
        and refund.reason == "Event cancelled."
    )
    assert refund.initiated_by_user_id == context.owner.id
    assert (
        await db_session.get(Campaign, campaign.id, populate_existing=True)
    ).redemption_count == 1
    assert await db_session.scalar(select(func.count()).select_from(PromoRedemption)) == 1
    notices = await event_notices(db_session)
    assert len(notices) == 2
    by_user = {notice.user_id: notice for notice in notices}
    for buyer, orders in [(context.buyer, [paid, pending]), (context.other_buyer, [free])]:
        notice = by_user[buyer.id]
        assert (
            notice.status == "queued" and notice.template_key == f"event_cancelled.{buyer.locale}"
        )
        assert notice.related_entity_id == str(context.event_id)
        assert notice.payload["ics_uid"] == uid and notice.payload["ics_sequence"] == 8
        assert set(notice.payload["order_ids"]) == {o["id"] for o in orders}
        assert notice.payload["to_email"] == buyer.email
    audit = await db_session.scalar(
        select(AuditLog).where(AuditLog.action_type == "event.cancelled")
    )
    assert audit.actor_user_id == context.owner.id and audit.actor_role == "organizer"
    assert audit.metadata_ == {
        "orders_refunded": 1,
        "orders_cancelled": 1,
        "orders_expired": 1,
        "event_notifications_queued": 2,
    }
    expiry = await db_session.scalar(
        select(AuditLog).where(AuditLog.action_type == "order.expired")
    )
    assert (
        expiry.actor_user_id == context.owner.id and expiry.metadata_["reason"] == "event_cancelled"
    )
    assert (await client.get(f"/api/v1/events/by-slug/{event.slug}")).status_code == 404
    assert (await checkout(client, context)).status_code == 409
    assert (await simulate(client, context, initiated["id"])).status_code == 409
    assert (await sweep_expired(db_session)) == 0
    for order in [paid, free, pending]:
        buyer = context.other_buyer if order is free else context.buyer
        detail = await client.get(f"/api/v1/orders/{order['id']}", headers=auth_headers(buyer))
        assert detail.status_code == 200
        assert detail.json()["status"] == (await fresh_order(db_session, order)).status


@pytest.mark.parametrize("seated", [False, True])
async def test_cancel_releases_pending_and_unattached_holds_without_altering_other_event(
    client, db_session, context, seated
):
    other_id = await create_event(db_session, context.profile)
    other_type = await create_ticket_type(db_session, other_id)
    seats = list((await db_session.scalars(select(Seat.id).order_by(Seat.id).limit(3))).all())
    if seated:
        await db_session.execute(
            update(Event)
            .where(Event.id == context.event_id)
            .values(
                venue_id=uuid.UUID("20000000-0000-0000-0000-000000000001"), seating_mode="assigned"
            )
        )
    attached = await create_seat_hold(
        db_session, context.event_id, seats[0], context.ticket_type.id, context.buyer
    )
    unattached = await create_seat_hold(
        db_session, context.event_id, seats[1], context.ticket_type.id, context.buyer
    )
    other = await create_seat_hold(db_session, other_id, seats[2], other_type.id, context.buyer)
    await db_session.commit()
    data = {
        "items": [
            {
                "ticket_type_id": str(context.ticket_type.id),
                "quantity": 1,
                **({"seat_hold_ids": [str(attached.id)]} if seated else {}),
            }
        ]
    }
    order = await placed_order(client, context, data=data)
    # Also cover an active hold attached to a GA order through the schema.
    if not seated:
        attached.order_id = uuid.UUID(order["id"])
        await db_session.commit()
    assert (await cancel_event(client, context)).status_code == 200
    for hold in [attached, unattached]:
        assert (
            await db_session.get(SeatHold, hold.id, populate_existing=True)
        ).status == "released"
    assert (await db_session.get(SeatHold, other.id, populate_existing=True)).status == "active"
    assert (await fresh_order(db_session, order)).status == "expired"
    assert (await db_session.get(Event, other_id, populate_existing=True)).status == "draft"


async def test_already_reversed_and_expired_orders_are_unchanged(client, db_session, context):
    refunded = await completed(client, db_session, context)
    assert (await reverse(client, context, refunded)).status_code == 201
    expired = await placed_order(client, context)
    await make_expired(db_session, expired)
    assert await sweep_expired(db_session) == 1
    free = await completed(client, db_session, context, paid=False)
    assert (await reverse(client, context, free, paid=False)).status_code == 200
    refunded_at = (await order_tickets(db_session, refunded))[0].invalidated_at
    cancelled_at = (await order_tickets(db_session, free))[0].invalidated_at
    assert (await cancel_event(client, context)).status_code == 200
    await assert_event_cancelled(db_session, context)
    assert (await order_tickets(db_session, refunded))[0].invalidated_at == refunded_at
    assert (await order_tickets(db_session, free))[0].invalidated_at == cancelled_at
    assert (await fresh_order(db_session, expired)).status == "expired"
    assert await db_session.scalar(select(func.count()).select_from(Refund)) == 1
    assert await event_notices(db_session) == []


@pytest.mark.parametrize(
    "state", [EventStatus.DRAFT, EventStatus.UNPUBLISHED, EventStatus.PUBLISHED]
)
@pytest.mark.parametrize("suspended", [False, True])
async def test_owner_can_cancel_any_live_publication_state_including_suspended(
    client, db_session, context, state, suspended
):
    order = await completed(client, db_session, context)
    await db_session.execute(
        update(Event)
        .where(Event.id == context.event_id)
        .values(status=state, is_suspended=suspended)
    )
    await db_session.commit()
    assert (await cancel_event(client, context)).status_code == 200
    await assert_event_cancelled(db_session, context)
    assert (await fresh_order(db_session, order)).status == "refunded"


@pytest.mark.parametrize(
    "role", ["buyer", "co_organizer", "event_admin", "support_agent", "platform_admin", "unrelated"]
)
async def test_event_cancellation_remains_owner_only(client, db_session, context, role):
    order = await completed(client, db_session, context)
    user = (
        context.buyer
        if role == "buyer"
        else context.co
        if role == "co_organizer"
        else await create_verified_user(db_session)
    )
    if role in {"event_admin", "support_agent"}:
        await create_staff_assignment(db_session, context.event_id, user, StaffRole(role))
    if role == "platform_admin":
        user.platform_role = PlatformRole.PLATFORM_ADMIN
    await db_session.commit()
    result = await cancel_event(client, context, user=user)
    assert result.status_code == (
        403 if role in {"co_organizer", "event_admin", "support_agent", "platform_admin"} else 404
    )
    assert (await fresh_order(db_session, order)).status == "completed"
    assert await event_notices(db_session) == []
    assert (
        await db_session.get(Event, context.event_id, populate_existing=True)
    ).status == "published"


async def test_cancellation_requires_auth_and_hides_missing_or_deleted_event(
    client, db_session, context
):
    assert (await client.post(f"/api/v1/events/{context.event_id}/cancel")).status_code == 401
    assert (
        await client.post(
            f"/api/v1/events/{uuid.uuid4()}/cancel", headers=auth_headers(context.owner)
        )
    ).status_code == 404
    await db_session.execute(
        update(Event).where(Event.id == context.event_id).values(deleted_at=datetime.now(UTC))
    )
    await db_session.commit()
    assert (await cancel_event(client, context)).status_code == 404


@pytest.mark.parametrize("paid", [False, True])
async def test_concurrent_and_repeated_cancellation_runs_cascade_once(
    client, db_session, context, paid
):
    await completed(client, db_session, context, paid=paid)
    results = await asyncio.gather(*(cancel_event(client, context) for _ in range(3)))
    assert all(r.status_code == 200 for r in results), [r.text for r in results]
    event = await assert_event_cancelled(db_session, context)
    timestamp, updated_at = event.cancelled_at, event.updated_at
    assert (await cancel_event(client, context)).status_code == 200
    event = await assert_event_cancelled(db_session, context)
    assert (event.cancelled_at, event.updated_at) == (timestamp, updated_at)
    assert len(await event_notices(db_session)) == 1
    assert await db_session.scalar(select(func.count()).select_from(Refund)) == int(paid)
    assert (
        await db_session.scalar(
            select(func.count())
            .select_from(AuditLog)
            .where(AuditLog.action_type == "event.cancelled")
        )
        == 1
    )


@pytest.mark.parametrize("failure", ["refund", "notice", "event_audit"])
async def test_failure_rolls_back_whole_cascade(client, db_session, context, monkeypatch, failure):
    campaign, _ = await add_promo(db_session, context)
    paid = await completed(client, db_session, context, promo_code="CHECKOUT15")
    pending = await placed_order(client, context, promo_code="CHECKOUT15")
    payment = await pay(client, context, pending["id"])
    seat_id = await db_session.scalar(select(Seat.id).limit(1))
    hold = await create_seat_hold(
        db_session, context.event_id, seat_id, context.ticket_type.id, context.buyer
    )
    await db_session.commit()
    if failure == "refund":
        await db_session.execute(
            update(Payment).where(Payment.order_id == uuid.UUID(paid["id"])).values(amount=1)
        )
        await db_session.commit()
    elif failure == "notice":
        enqueue = cancellation.notifications.enqueue

        async def fail_notice(*args, **kwargs):
            if kwargs["type"] == NotificationType.EVENT_CANCELLED:
                raise RuntimeError("outbox failure")
            return await enqueue(*args, **kwargs)

        monkeypatch.setattr(cancellation.notifications, "enqueue", fail_notice)
    else:
        audit = events.audit

        async def fail_audit(session, access, action, *args, **kwargs):
            if action == "event.cancelled":
                raise RuntimeError("audit failure")
            return await audit(session, access, action, *args, **kwargs)

        monkeypatch.setattr(events, "audit", fail_audit)
    result = await cancel_event(client, context)
    assert result.status_code == (409 if failure == "refund" else 500), result.text
    event = await db_session.get(Event, context.event_id, populate_existing=True)
    assert event.status == "published" and event.cancelled_at is None and event.ics_sequence == 0
    assert event.paid_sales_status == "active"
    assert (await fresh_order(db_session, paid)).status == "completed"
    assert (await fresh_order(db_session, pending)).status == "awaiting_payment"
    assert (
        await db_session.get(Payment, uuid.UUID(payment["id"]), populate_existing=True)
    ).status == "initiated"
    assert all(
        t.status == "valid" and t.invalidated_at is None
        for t in await order_tickets(db_session, paid)
    )
    ticket_type = await db_session.get(TicketType, context.ticket_type.id, populate_existing=True)
    assert ticket_type.quantity_sold == 2 and ticket_type.quantity_reserved == 1
    assert await db_session.scalar(select(func.count()).select_from(Refund)) == 0
    assert await event_notices(db_session) == []
    assert (
        await db_session.scalar(
            select(func.count())
            .select_from(AuditLog)
            .where(
                AuditLog.action_type.in_(
                    ["order.refunded", "order.expired", "payment.cancelled", "event.cancelled"]
                )
            )
        )
        == 0
    )
    assert (
        await db_session.get(Campaign, campaign.id, populate_existing=True)
    ).redemption_count == 2
    assert await db_session.scalar(select(func.count()).select_from(PromoRedemption)) == 2
    assert (await db_session.get(SeatHold, hold.id, populate_existing=True)).status == "active"
    assert (
        await db_session.scalar(
            select(func.count())
            .select_from(Notification)
            .where(Notification.type == NotificationType.REFUND_COMPLETED)
        )
        == 0
    )


@pytest.mark.parametrize(
    "state", [OrderStatus.PAID, OrderStatus.PARTIALLY_REFUNDED, OrderStatus.CANCELLED]
)
async def test_inconsistent_orders_never_leave_cancelled_event_with_active_tickets(
    client, db_session, context, state
):
    order = await completed(client, db_session, context)
    await db_session.execute(
        update(Order).where(Order.id == uuid.UUID(order["id"])).values(status=state)
    )
    await db_session.commit()
    result = await cancel_event(client, context)
    assert (
        result.status_code == 409
        and result.json()["error"]["code"] == "EVENT_CANCELLATION_STATE_INVALID"
    )
    assert (
        await db_session.get(Event, context.event_id, populate_existing=True)
    ).status == "published"
    assert await db_session.scalar(select(func.count()).select_from(Refund)) == 0


@pytest.mark.parametrize("paid", [False, True])
async def test_checkout_racing_cancellation_never_leaves_live_inventory(
    client, db_session, context, paid
):
    if not paid:
        await db_session.execute(
            update(TicketType).where(TicketType.id == context.ticket_type.id).values(price_amount=0)
        )
        await db_session.commit()
    purchase, cancelled = await asyncio.gather(
        checkout(client, context), cancel_event(client, context)
    )
    assert cancelled.status_code == 200, cancelled.text
    assert purchase.status_code in {201, 409}, purchase.text
    await assert_event_cancelled(db_session, context)
    if purchase.status_code == 201:
        assert (await fresh_order(db_session, purchase.json())).status == (
            "expired" if paid else "cancelled"
        )
    assert (await checkout(client, context)).status_code == 409


async def test_payment_confirmation_racing_cancellation_refunds_or_cancels_once(
    client, db_session, context
):
    order = await placed_order(client, context)
    payment = await pay(client, context, order["id"])
    confirmed, cancelled = await asyncio.gather(
        simulate(client, context, payment["id"]), cancel_event(client, context)
    )
    assert cancelled.status_code == 200 and confirmed.status_code in {200, 409}, [
        confirmed.text,
        cancelled.text,
    ]
    await assert_event_cancelled(db_session, context)
    current = await fresh_order(db_session, order)
    captured = confirmed.status_code == 200
    assert current.status == ("refunded" if captured else "expired")
    assert await db_session.scalar(select(func.count()).select_from(Refund)) == int(captured)
    assert len(await order_tickets(db_session, order)) == int(captured)


async def test_individual_refund_racing_event_cancellation_does_not_refund_twice(
    client, db_session, context
):
    order = await completed(client, db_session, context)
    refunded, cancelled = await asyncio.gather(
        reverse(client, context, order), cancel_event(client, context)
    )
    assert cancelled.status_code == 200 and refunded.status_code in {201, 409}, [
        refunded.text,
        cancelled.text,
    ]
    await assert_event_cancelled(db_session, context)
    assert await db_session.scalar(select(func.count()).select_from(Refund)) == 1
    assert (await fresh_order(db_session, order)).status == "refunded"


@pytest.mark.parametrize("paid", [False, True])
async def test_checkin_record_can_commit_while_cancellation_owns_event_lock(
    client, db_session, context, monkeypatch, paid
):
    order = await completed(client, db_session, context, paid=paid, quantity=1)
    ticket = (await order_tickets(db_session, order))[0]
    await db_session.commit()
    ticket_locked, event_locked = asyncio.Event(), asyncio.Event()
    append, cascade = checkin.append_record, cancellation.cascade_locked

    async def paused_append(*args, **kwargs):
        ticket_locked.set()
        await asyncio.wait_for(event_locked.wait(), timeout=5)
        return await append(*args, **kwargs)

    async def observed_cascade(*args, **kwargs):
        event_locked.set()
        return await cascade(*args, **kwargs)

    async def cancel_after_scan():
        await asyncio.wait_for(ticket_locked.wait(), timeout=5)
        return await cancel_event(client, context)

    monkeypatch.setattr(checkin, "append_record", paused_append)
    monkeypatch.setattr(cancellation, "cascade_locked", observed_cascade)
    scanned, cancelled = await asyncio.wait_for(
        asyncio.gather(
            client.post(
                f"/api/v1/checkin/scan?event_id={context.event_id}",
                json={"token": ticket.qr_token},
                headers=auth_headers(context.owner),
            ),
            cancel_after_scan(),
        ),
        timeout=10,
    )
    assert scanned.status_code == 201 and scanned.json()["result"] == "valid", scanned.text
    assert cancelled.status_code == 200, cancelled.text
    await assert_event_cancelled(db_session, context)
    assert await db_session.scalar(select(func.count()).select_from(CheckInRecord)) == 1
    late = await client.post(
        f"/api/v1/checkin/scan?event_id={context.event_id}",
        json={"token": ticket.qr_token},
        headers=auth_headers(context.owner),
    )
    assert late.status_code == 201 and late.json()["result"] == (
        "refunded" if paid else "cancelled"
    )


async def test_cancellation_does_not_reverse_orders_for_other_events(client, db_session, context):
    await completed(client, db_session, context)
    other_id = await create_event(
        db_session,
        context.profile,
        status=EventStatus.PUBLISHED,
        paid_sales_status=PaidSalesStatus.ACTIVE,
    )
    other_type = await create_ticket_type(db_session, other_id)
    await db_session.commit()
    other = SimpleNamespace(**{**vars(context), "event_id": other_id, "ticket_type": other_type})
    order = await completed(client, db_session, other)
    assert (await cancel_event(client, context)).status_code == 200
    assert (await fresh_order(db_session, order)).status == "completed"
    assert all(t.status == "valid" for t in await order_tickets(db_session, order))
    assert (await db_session.get(Event, other_id, populate_existing=True)).status == "published"
    assert (
        await db_session.get(TicketType, other_type.id, populate_existing=True)
    ).quantity_sold == 2


async def test_empty_event_cancellation_updates_calendar_once(client, db_session, context):
    before = await db_session.get(Event, context.event_id)
    uid = before.ics_uid
    assert (await cancel_event(client, context)).status_code == 200
    event = await assert_event_cancelled(db_session, context)
    assert event.ics_uid == uid and await event_notices(db_session) == []
    assert (await cancel_event(client, context)).status_code == 200
    await assert_event_cancelled(db_session, context)


async def test_sweeper_racing_cancellation_releases_promo_and_inventory_once(
    client, db_session, context, test_sessionmaker
):
    campaign, _ = await add_promo(db_session, context)
    order = await placed_order(client, context, promo_code="CHECKOUT15")
    payment = await pay(client, context, order["id"])
    await make_expired(db_session, order)

    async def sweep():
        async with test_sessionmaker() as session:
            return await sweep_expired(session)

    cancelled, swept = await asyncio.gather(cancel_event(client, context), sweep())
    assert cancelled.status_code == 200 and swept in {0, 1}, cancelled.text
    await assert_event_cancelled(db_session, context)
    assert (await fresh_order(db_session, order)).status == "expired"
    assert (
        await db_session.get(Payment, uuid.UUID(payment["id"]), populate_existing=True)
    ).status == "cancelled"
    assert (
        await db_session.get(Campaign, campaign.id, populate_existing=True)
    ).redemption_count == 0
    assert await db_session.scalar(select(func.count()).select_from(PromoRedemption)) == 0
    assert (
        await db_session.scalar(
            select(func.count())
            .select_from(AuditLog)
            .where(AuditLog.action_type == "payment.cancelled")
        )
        == 1
    )
