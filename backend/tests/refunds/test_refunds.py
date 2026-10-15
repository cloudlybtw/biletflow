import asyncio
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select, update

from app.db.settings import PlatformSetting
from app.modules.campaigns.models import Campaign
from app.modules.checkin import service as checkin_service
from app.modules.checkin.models import CheckInRecord
from app.modules.history.models import AuditLog
from app.modules.notifications.models import Notification, NotificationType
from app.modules.orders.models import Order, OrderItem, OrderStatus, PromoRedemption
from app.modules.payments.models import Payment
from app.modules.refunds import service
from app.modules.refunds.models import Refund
from app.modules.ticketing.holds import SeatHold
from app.modules.ticketing.models import TicketType
from app.modules.tickets.models import Ticket
from app.modules.users.models import PlatformRole, StaffAssignment, StaffRole
from app.modules.venues.models import Seat, VenueRow
from tests.factories import (
    auth_headers,
    create_event,
    create_staff_assignment,
    create_ticket_type,
    create_verified_user,
)
from tests.orders.conftest import add_promo
from tests.orders.helpers import checkout, pay, placed_order, simulate


async def reverse(client, context, order, *, paid=True, user=None, data=None, event_id=None):
    return await client.post(
        f"/api/v1/events/{event_id or context.event_id}/orders/{order['id']}/"
        + ("refunds" if paid else "cancel"),
        json={"reason": "Organizer request"} if data is None else data,
        headers=auth_headers(user or context.owner),
    )


async def completed(client, db_session, context, *, paid=True, quantity=2, **extra):
    if not paid:
        await db_session.execute(
            update(TicketType).where(TicketType.id == context.ticket_type.id).values(price_amount=0)
        )
        await db_session.commit()
    order = await placed_order(client, context, quantity=quantity, **extra)
    if paid:
        payment = await pay(client, context, order["id"])
        response = await simulate(client, context, payment["id"])
        assert response.status_code == 200, response.text
    return order


async def order_tickets(db_session, order):
    return list(
        (
            await db_session.scalars(
                select(Ticket)
                .join(OrderItem, OrderItem.id == Ticket.order_item_id)
                .where(OrderItem.order_id == uuid.UUID(order["id"]))
                .order_by(Ticket.id)
                .execution_options(populate_existing=True)
            )
        ).all()
    )


@pytest.mark.parametrize("paid", [False, True])
async def test_full_reversal_invalidates_tickets_returns_inventory_and_notifies(
    client, db_session, context, paid
):
    order = await completed(client, db_session, context, paid=paid)
    before = await db_session.get(Order, uuid.UUID(order["id"]), populate_existing=True)
    before_updated = before.updated_at
    response = await reverse(
        client, context, order, paid=paid, data={"reason": "  Cancelled by host  "}
    )
    assert response.status_code == (201 if paid else 200), response.text
    body = response.json()
    assert body["order_id"] == order["id"]
    tickets = await order_tickets(db_session, order)
    assert len(tickets) == 2
    assert all(
        t.status == ("refunded" if paid else "cancelled") and t.invalidated_at for t in tickets
    )
    current = await db_session.get(Order, before.id, populate_existing=True)
    assert current.status == ("refunded" if paid else "cancelled")
    assert current.updated_at > before_updated
    inventory = await db_session.get(TicketType, context.ticket_type.id, populate_existing=True)
    assert inventory.quantity_sold == inventory.quantity_reserved == 0
    kind = NotificationType.REFUND_COMPLETED if paid else NotificationType.EVENT_UPDATE
    notification = await db_session.scalar(select(Notification).where(Notification.type == kind))
    assert notification.status == "queued" and notification.user_id == context.buyer.id
    assert notification.payload["reason"] == "Cancelled by host"
    assert notification.payload["to_email"] == context.buyer.email
    assert notification.related_entity_id == order["id"]
    audit = await db_session.scalar(
        select(AuditLog).where(
            AuditLog.action_type == ("order.refunded" if paid else "order.cancelled")
        )
    )
    assert audit.actor_user_id == context.owner.id and audit.actor_role == "organizer"
    if paid:
        assert body["simulated"] is True and body["status"] == "completed"
        assert body["amount"] == 2000 and body["currency"] == "KZT"
        assert body["initiated_by_user_id"] == str(context.owner.id)
        assert body["provider_refund_ref"].startswith("sim_refund_") and body["processed_at"]
        payment = await db_session.get(Payment, uuid.UUID(body["payment_id"]))
        assert payment.status == "succeeded"
        assert await db_session.scalar(select(func.count()).select_from(Refund)) == 1
        assert (
            await db_session.scalar(
                select(func.count())
                .select_from(AuditLog)
                .where(AuditLog.action_type == "refund.completed")
            )
            == 1
        )
    else:
        assert set(body["ticket_ids"]) == {str(t.id) for t in tickets}
        assert await db_session.scalar(select(func.count()).select_from(Refund)) == 0
    detail = await client.get(f"/api/v1/orders/{order['id']}", headers=auth_headers(context.buyer))
    assert detail.status_code == 200 and detail.json()["status"] == current.status
    for ticket in tickets:
        scan = await client.post(
            f"/api/v1/checkin/scan?event_id={context.event_id}",
            json={"token": ticket.qr_token},
            headers=auth_headers(context.owner),
        )
        assert scan.json()["result"] == ("refunded" if paid else "cancelled")


async def test_refund_uses_captured_discounted_total_including_fee_and_retains_promo_history(
    client, db_session, context
):
    campaign, _ = await add_promo(db_session, context)
    await db_session.execute(
        update(PlatformSetting)
        .where(PlatformSetting.key == "processing_fee_percent")
        .values(value=10)
    )
    await db_session.commit()
    order = await completed(client, db_session, context, promo_code="CHECKOUT15")
    assert order["total_amount"] == 1870
    response = await reverse(client, context, order)
    assert response.status_code == 201, response.text
    assert response.json()["amount"] == 1870
    assert (
        await db_session.get(Campaign, campaign.id, populate_existing=True)
    ).redemption_count == 1
    assert await db_session.scalar(select(func.count()).select_from(PromoRedemption)) == 1


async def test_fully_discounted_order_cancels_as_free(client, db_session, context):
    await add_promo(db_session, context, value=100)
    order = await placed_order(client, context, promo_code="CHECKOUT15")
    assert order["total_amount"] == 0 and order["status"] == "completed"
    assert (await reverse(client, context, order, paid=False)).status_code == 200
    assert await db_session.scalar(select(func.count()).select_from(Refund)) == 0


@pytest.mark.parametrize("paid", [False, True])
async def test_co_organizer_may_reverse_order(client, db_session, context, paid):
    order = await completed(client, db_session, context, paid=paid)
    response = await reverse(client, context, order, paid=paid, user=context.co)
    assert response.status_code == (201 if paid else 200), response.text
    audit = await db_session.scalar(
        select(AuditLog).where(
            AuditLog.action_type == ("order.refunded" if paid else "order.cancelled")
        )
    )
    assert audit.actor_role == "co_organizer" and audit.actor_user_id == context.co.id


@pytest.mark.parametrize("paid", [False, True])
@pytest.mark.parametrize(
    "role", ["buyer", "unrelated", "event_admin", "support_agent", "revoked", "platform_admin"]
)
async def test_reversal_requires_owner_or_active_co_organizer(
    client, db_session, context, paid, role
):
    order = await completed(client, db_session, context, paid=paid)
    user = context.buyer if role == "buyer" else await create_verified_user(db_session)
    if role in {"event_admin", "support_agent"}:
        await create_staff_assignment(db_session, context.event_id, user, StaffRole(role))
    if role == "platform_admin":
        user.platform_role = PlatformRole.PLATFORM_ADMIN
    if role == "revoked":
        user = context.co
        await db_session.execute(
            update(StaffAssignment)
            .where(StaffAssignment.id == context.assignment.id)
            .values(revoked_at=datetime.now(UTC))
        )
    await db_session.commit()
    response = await reverse(client, context, order, paid=paid, user=user)
    assert response.status_code == (
        403 if role in {"event_admin", "support_agent", "platform_admin"} else 404
    )
    assert (
        await db_session.get(Order, uuid.UUID(order["id"]), populate_existing=True)
    ).status == "completed"
    assert await db_session.scalar(select(func.count()).select_from(Refund)) == 0
    assert (
        await db_session.get(TicketType, context.ticket_type.id, populate_existing=True)
    ).quantity_sold == 2


@pytest.mark.parametrize("paid", [False, True])
async def test_reversal_requires_auth_and_hides_other_event_orders(
    client, db_session, context, paid
):
    order = await completed(client, db_session, context, paid=paid)
    suffix = "refunds" if paid else "cancel"
    path = f"/api/v1/events/{context.event_id}/orders/{order['id']}/{suffix}"
    assert (await client.post(path, json={})).status_code == 401
    other_event = await create_event(db_session, context.profile)
    await db_session.commit()
    for event_id, order_id in [(other_event, order["id"]), (context.event_id, str(uuid.uuid4()))]:
        response = await reverse(client, context, {"id": order_id}, paid=paid, event_id=event_id)
        assert response.status_code == 404


@pytest.mark.parametrize("paid", [False, True])
async def test_free_and_paid_endpoints_reject_wrong_order_kind(client, db_session, context, paid):
    order = await completed(client, db_session, context, paid=paid)
    response = await reverse(client, context, order, paid=not paid)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == ("ORDER_NOT_FREE" if paid else "ORDER_NOT_PAID")


@pytest.mark.parametrize("state", [s for s in OrderStatus if s != OrderStatus.COMPLETED])
async def test_refund_rejects_every_non_completed_order_state(client, db_session, context, state):
    order = await placed_order(client, context)
    await db_session.execute(
        update(Order).where(Order.id == uuid.UUID(order["id"])).values(status=state)
    )
    await db_session.commit()
    response = await reverse(client, context, order)
    assert response.status_code == 409 and response.json()["error"]["code"] == "ORDER_NOT_COMPLETED"
    assert await db_session.scalar(select(func.count()).select_from(Refund)) == 0


@pytest.mark.parametrize("paid", [False, True])
async def test_duplicate_reversal_race_has_one_winner_and_returns_inventory_once(
    client, db_session, context, paid
):
    order = await completed(client, db_session, context, paid=paid)
    # Each HTTP request receives a separate AsyncSession from get_session.
    results = await asyncio.gather(*(reverse(client, context, order, paid=paid) for _ in range(3)))
    assert sorted(r.status_code for r in results) == [201 if paid else 200, 409, 409], [
        r.text for r in results
    ]
    replay = await reverse(client, context, order, paid=paid)
    assert replay.status_code == 409
    assert (
        await db_session.get(TicketType, context.ticket_type.id, populate_existing=True)
    ).quantity_sold == 0
    assert await db_session.scalar(select(func.count()).select_from(Refund)) == int(paid)
    kind = NotificationType.REFUND_COMPLETED if paid else NotificationType.EVENT_UPDATE
    assert (
        await db_session.scalar(
            select(func.count()).select_from(Notification).where(Notification.type == kind)
        )
        == 1
    )


@pytest.mark.parametrize("paid", [False, True])
@pytest.mark.parametrize("failure", ["audit", "notification"])
async def test_reversal_rolls_back_all_changes_on_audit_or_notification_failure(
    client, db_session, context, monkeypatch, paid, failure
):
    order = await completed(client, db_session, context, paid=paid)

    async def fail(*args, **kwargs):
        raise RuntimeError("simulated persistence failure")

    monkeypatch.setattr(
        service.history if failure == "audit" else service.notifications,
        "record" if failure == "audit" else "enqueue",
        fail,
    )
    response = await reverse(client, context, order, paid=paid)
    assert response.status_code == 500
    assert (
        await db_session.get(Order, uuid.UUID(order["id"]), populate_existing=True)
    ).status == "completed"
    assert (
        await db_session.get(TicketType, context.ticket_type.id, populate_existing=True)
    ).quantity_sold == 2
    assert all(
        t.status == "valid" and t.invalidated_at is None
        for t in await order_tickets(db_session, order)
    )
    assert await db_session.scalar(select(func.count()).select_from(Refund)) == 0
    assert (
        await db_session.scalar(
            select(func.count())
            .select_from(AuditLog)
            .where(
                AuditLog.action_type.in_(["order.refunded", "order.cancelled", "refund.completed"])
            )
        )
        == 0
    )


@pytest.mark.parametrize("paid", [False, True])
async def test_scan_racing_reversal_cannot_restore_invalidated_ticket(
    client, db_session, context, paid
):
    order = await completed(client, db_session, context, paid=paid, quantity=1)
    ticket = (await order_tickets(db_session, order))[0]
    await db_session.commit()
    scan, reversal = await asyncio.gather(
        client.post(
            f"/api/v1/checkin/scan?event_id={context.event_id}",
            json={"token": ticket.qr_token},
            headers=auth_headers(context.owner),
        ),
        reverse(client, context, order, paid=paid),
    )
    assert reversal.status_code == (201 if paid else 200), reversal.text
    assert scan.status_code == 201 and scan.json()["result"] in {
        "valid",
        "refunded" if paid else "cancelled",
    }
    refreshed = await db_session.get(Ticket, ticket.id, populate_existing=True)
    assert refreshed.status == ("refunded" if paid else "cancelled")
    if scan.json()["result"] == "valid":
        assert refreshed.checked_in_at is not None
        undo = await client.post(
            f"/api/v1/events/{context.event_id}/checkin/records/{scan.json()['record_id']}/reverse",
            json={},
            headers=auth_headers(context.owner),
        )
        assert undo.status_code == 409, undo.text


async def test_payment_callback_replay_after_refund_never_reissues_tickets(
    client, db_session, context
):
    order = await completed(client, db_session, context)
    refund = (await reverse(client, context, order)).json()
    replay = await simulate(client, context, refund["payment_id"])
    assert replay.status_code == 200 and replay.json()["status"] == "succeeded"
    assert (
        await db_session.get(Order, uuid.UUID(order["id"]), populate_existing=True)
    ).status == "refunded"
    assert all(t.status == "refunded" for t in await order_tickets(db_session, order))
    assert (
        await db_session.get(TicketType, context.ticket_type.id, populate_existing=True)
    ).quantity_sold == 0


@pytest.mark.parametrize("bad_data", [{"amount": 1}, {"reason": " "}, {"reason": "x" * 2001}])
async def test_refund_does_not_accept_client_amount_or_invalid_reason(
    client, db_session, context, bad_data
):
    order = await completed(client, db_session, context)
    assert (await reverse(client, context, order, data=bad_data)).status_code == 422


@pytest.mark.parametrize(
    "broken", ["amount", "provider", "not_simulated", "missing_payment", "inventory"]
)
async def test_inconsistent_payment_or_inventory_fails_atomically(
    client, db_session, context, broken
):
    order = await completed(client, db_session, context)
    if broken == "inventory":
        await db_session.execute(
            update(TicketType)
            .where(TicketType.id == context.ticket_type.id)
            .values(quantity_sold=0)
        )
    else:
        changes = (
            {"amount": 1}
            if broken == "amount"
            else {"provider": "other"}
            if broken == "provider"
            else {"is_simulated": False}
            if broken == "not_simulated"
            else {"status": "failed"}
        )
        await db_session.execute(
            update(Payment).where(Payment.order_id == uuid.UUID(order["id"])).values(**changes)
        )
    await db_session.commit()
    result = await reverse(client, context, order)
    assert result.status_code == 409, result.text
    assert (
        await db_session.get(Order, uuid.UUID(order["id"]), populate_existing=True)
    ).status == "completed"
    assert all(t.status == "valid" for t in await order_tickets(db_session, order))
    assert await db_session.scalar(select(func.count()).select_from(Refund)) == 0


@pytest.mark.parametrize("paid", [False, True])
async def test_reversal_returns_inventory_for_resale(client, db_session, context, paid):
    await db_session.execute(
        update(TicketType).where(TicketType.id == context.ticket_type.id).values(quantity_total=2)
    )
    await db_session.commit()
    order = await completed(client, db_session, context, paid=paid)
    assert (await checkout(client, context, buyer=context.other_buyer)).status_code == 409
    assert (await reverse(client, context, order, paid=paid)).status_code == (201 if paid else 200)
    assert (
        await checkout(client, context, buyer=context.other_buyer, quantity=2)
    ).status_code == 201


async def test_cancelled_assigned_seat_can_be_sold_again(client, db_session, context):
    from app.modules.events.models import Event

    venue_id = uuid.UUID("20000000-0000-0000-0000-000000000001")
    await db_session.execute(
        update(Event)
        .where(Event.id == context.event_id)
        .values(venue_id=venue_id, seating_mode="assigned")
    )
    await db_session.execute(
        update(TicketType).where(TicketType.id == context.ticket_type.id).values(price_amount=0)
    )
    seat_id = await db_session.scalar(
        select(Seat.id).join(VenueRow).where(VenueRow.label == "A").limit(1)
    )

    async def hold_for(buyer):
        hold = SeatHold(
            event_id=context.event_id,
            seat_id=seat_id,
            ticket_type_id=context.ticket_type.id,
            held_by_user_id=buyer.id,
            session_token="refund-seat-test",
            expires_at=datetime.now(UTC) + timedelta(minutes=10),
        )
        db_session.add(hold)
        await db_session.commit()
        return {
            "items": [
                {
                    "ticket_type_id": str(context.ticket_type.id),
                    "quantity": 1,
                    "seat_hold_ids": [str(hold.id)],
                }
            ]
        }

    order = await placed_order(client, context, data=await hold_for(context.buyer))
    assert (await reverse(client, context, order, paid=False)).status_code == 200
    response = await checkout(
        client, context, buyer=context.other_buyer, data=await hold_for(context.other_buyer)
    )
    assert response.status_code == 201, response.text
    tickets = list(
        (await db_session.scalars(select(Ticket).where(Ticket.seat_id == seat_id))).all()
    )
    assert sorted(t.status for t in tickets) == ["cancelled", "valid"]


@pytest.mark.parametrize("paid", [False, True])
async def test_scan_audit_can_finish_while_reversal_holds_event_lock(
    client, db_session, context, monkeypatch, paid
):
    order = await completed(client, db_session, context, paid=paid, quantity=1)
    ticket = (await order_tickets(db_session, order))[0]
    await db_session.commit()
    ticket_locked = asyncio.Event()
    event_locked = asyncio.Event()
    append_record = checkin_service.append_record
    lock_order = service.orders.lock_order

    async def paused_append(*args, **kwargs):
        ticket_locked.set()
        await asyncio.wait_for(event_locked.wait(), timeout=5)
        return await append_record(*args, **kwargs)

    async def observed_lock(*args, **kwargs):
        locked = await lock_order(*args, **kwargs)
        event_locked.set()
        return locked

    monkeypatch.setattr(checkin_service, "append_record", paused_append)
    monkeypatch.setattr(service.orders, "lock_order", observed_lock)

    async def reverse_after_scan_locks_ticket():
        await asyncio.wait_for(ticket_locked.wait(), timeout=5)
        return await reverse(client, context, order, paid=paid)

    scan, reversal = await asyncio.wait_for(
        asyncio.gather(
            client.post(
                f"/api/v1/checkin/scan?event_id={context.event_id}",
                json={"token": ticket.qr_token},
                headers=auth_headers(context.owner),
            ),
            reverse_after_scan_locks_ticket(),
        ),
        timeout=10,
    )
    assert scan.status_code == 201 and scan.json()["result"] == "valid", scan.text
    assert reversal.status_code == (201 if paid else 200), reversal.text
    refreshed = await db_session.get(Ticket, ticket.id, populate_existing=True)
    assert refreshed.status == ("refunded" if paid else "cancelled")
    assert refreshed.checked_in_at is not None and refreshed.invalidated_at is not None
    assert await db_session.scalar(select(func.count()).select_from(CheckInRecord)) == 1


async def test_full_refund_returns_every_ticket_type_in_a_mixed_order(client, db_session, context):
    free = await create_ticket_type(db_session, context.event_id, price_amount=0)
    premium = await create_ticket_type(db_session, context.event_id, price_amount=2500)
    await db_session.commit()
    order = await completed(
        client,
        db_session,
        context,
        data={
            "items": [
                {"ticket_type_id": str(context.ticket_type.id), "quantity": 2},
                {"ticket_type_id": str(free.id), "quantity": 1},
                {"ticket_type_id": str(premium.id), "quantity": 3},
            ]
        },
    )
    result = await reverse(client, context, order, data={})
    assert result.status_code == 201 and result.json()["amount"] == 9500, result.text
    for ticket_type in [context.ticket_type, free, premium]:
        current = await db_session.get(TicketType, ticket_type.id, populate_existing=True)
        assert current.quantity_reserved == current.quantity_sold == 0
    assert len(await order_tickets(db_session, order)) == 6
    assert all(t.status == "refunded" for t in await order_tickets(db_session, order))
