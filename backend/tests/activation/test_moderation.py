import asyncio

import pytest
from sqlalchemy import func, select, update

from app.modules.activation.models import PaidSalesActivation
from app.modules.events.models import Event
from app.modules.history.models import AuditLog
from app.modules.orders.models import Order
from app.modules.organizers.models import PayoutAccount
from app.modules.ticketing.models import TicketType
from app.modules.tickets.models import Ticket
from tests.activation.test_activation import post, prepare
from tests.factories import auth_headers, create_ticket_type


async def moderate(client, ctx, suffix, *, user=None):
    return await client.post(
        f"/api/v1/admin/events/{ctx.event_id}" + suffix,
        headers=auth_headers(user or ctx.admin),
        json={"reason": "Suspicious activity"} if suffix.endswith("/suspend") else None,
    )


async def buy(client, ctx, ticket=None):
    return await client.post(
        f"/api/v1/events/{ctx.event_id}/orders",
        headers=auth_headers(ctx.other),
        json={"items": [{"ticket_type_id": str((ticket or ctx.ticket).id), "quantity": 1}]},
    )


async def test_paid_suspension_blocks_paid_checkout_but_allows_free_registration(
    client, db_session, ctx
):
    await prepare(client, db_session, ctx)
    activated = await post(client, ctx, "/activate", {})
    assert activated.status_code == 200
    free = await create_ticket_type(db_session, ctx.event_id, price_amount=0)
    await db_session.commit()
    first = await moderate(client, ctx, "/paid-sales/suspend")
    assert first.status_code == 200 and first.json()["paid_sales_status"] == "suspended"
    assert (await buy(client, ctx)).json()["error"]["code"] == "PAID_SALES_INACTIVE"
    assert (await buy(client, ctx, free)).status_code == 201
    assert (await post(client, ctx, "/activate", {})).json()["error"][
        "code"
    ] == "PAID_SALES_SUSPENDED"
    assert (await post(client, ctx, "/pay")).status_code == 409
    assert (await moderate(client, ctx, "/paid-sales/suspend")).status_code == 200
    restored = await moderate(client, ctx, "/paid-sales/unsuspend")
    assert restored.status_code == 200 and restored.json()["paid_sales_status"] == "active"
    assert (await buy(client, ctx)).status_code == 201
    activation = await db_session.scalar(select(PaidSalesActivation))
    assert activation.status == "active" and activation.suspended_at is None
    assert (
        await db_session.scalar(
            select(func.count())
            .select_from(AuditLog)
            .where(AuditLog.action_type == "paid_sales.suspended")
        )
        == 1
    )


async def test_event_suspension_blocks_free_and_paid_orders_and_pending_payment(
    client, db_session, ctx
):
    await prepare(client, db_session, ctx)
    assert (await post(client, ctx, "/activate", {})).status_code == 200
    order = (await buy(client, ctx)).json()
    payment = await client.post(
        f"/api/v1/orders/{order['id']}/pay", headers=auth_headers(ctx.other)
    )
    assert payment.status_code == 201
    free = await create_ticket_type(db_session, ctx.event_id, price_amount=0)
    await db_session.commit()
    suspended = await moderate(client, ctx, "/suspend")
    assert suspended.status_code == 200 and suspended.json()["is_suspended"]
    event = await db_session.get(Event, ctx.event_id, populate_existing=True)
    assert event.status == "published" and event.suspension_reason == "Suspicious activity"
    for ticket in [ctx.ticket, free]:
        blocked = await buy(client, ctx, ticket)
        assert blocked.status_code == 409 and blocked.json()["error"]["code"] == "EVENT_SUSPENDED"
    completion = await client.post(
        f"/api/v1/payments/{payment.json()['id']}/simulate",
        headers=auth_headers(ctx.other),
        json={"outcome": "success"},
    )
    assert completion.status_code == 409
    assert await db_session.scalar(select(func.count()).select_from(Ticket)) == 0
    assert (await client.get(f"/api/v1/events/by-slug/{event.slug}")).status_code == 404
    assert (await client.get(f"/api/v1/events/{event.id}/ticket-types")).status_code == 404
    assert (
        await client.post(f"/api/v1/events/{event.id}/publish", headers=auth_headers(ctx.owner))
    ).json()["error"]["code"] == "EVENT_SUSPENDED"
    restored = await moderate(client, ctx, "/unsuspend")
    assert restored.status_code == 200 and not restored.json()["is_suspended"]
    assert (
        await client.post(
            f"/api/v1/payments/{payment.json()['id']}/simulate",
            headers=auth_headers(ctx.other),
            json={"outcome": "success"},
        )
    ).status_code == 200
    assert await db_session.scalar(select(func.count()).select_from(Ticket)) == 1
    audit = await db_session.scalar(
        select(AuditLog).where(AuditLog.action_type == "event.suspended")
    )
    assert audit.actor_user_id == ctx.admin.id and audit.actor_role == "platform_admin"
    assert audit.metadata_["reason"] == "Suspicious activity"


async def test_paid_suspension_blocks_existing_payment_confirmation(client, db_session, ctx):
    await prepare(client, db_session, ctx)
    assert (await post(client, ctx, "/activate", {})).status_code == 200
    order = (await buy(client, ctx)).json()
    payment = (
        await client.post(f"/api/v1/orders/{order['id']}/pay", headers=auth_headers(ctx.other))
    ).json()
    assert (await moderate(client, ctx, "/paid-sales/suspend")).status_code == 200
    result = await client.post(
        f"/api/v1/payments/{payment['id']}/simulate",
        headers=auth_headers(ctx.other),
        json={"outcome": "success"},
    )
    assert result.status_code == 409 and result.json()["error"]["code"] == "PAID_SALES_INACTIVE"
    assert await db_session.scalar(select(func.count()).select_from(Ticket)) == 0


async def test_independent_suspensions_do_not_restore_each_other(client, db_session, ctx):
    await prepare(client, db_session, ctx)
    assert (await post(client, ctx, "/activate", {})).status_code == 200
    assert (await moderate(client, ctx, "/suspend")).status_code == 200
    assert (await moderate(client, ctx, "/paid-sales/suspend")).status_code == 200
    first = await moderate(client, ctx, "/unsuspend")
    assert first.json()["paid_sales_status"] == "suspended"
    assert (await buy(client, ctx)).status_code == 409
    assert (await moderate(client, ctx, "/suspend")).status_code == 200
    second = await moderate(client, ctx, "/paid-sales/unsuspend")
    assert second.json()["is_suspended"] and second.json()["paid_sales_status"] == "active"
    assert (await buy(client, ctx)).json()["error"]["code"] == "EVENT_SUSPENDED"


async def test_unsuspend_never_activates_unpaid_event(client, ctx):
    assert (await moderate(client, ctx, "/paid-sales/suspend")).status_code == 200
    assert (await post(client, ctx, "/pay")).status_code == 409
    restored = await moderate(client, ctx, "/paid-sales/unsuspend")
    assert restored.json()["paid_sales_status"] == "disabled"
    assert (await buy(client, ctx)).status_code == 409


async def test_pending_activation_survives_suspension_without_becoming_active(
    client, db_session, ctx
):
    payment = await post(client, ctx, "/pay")
    assert payment.status_code == 201
    assert (await moderate(client, ctx, "/paid-sales/suspend")).status_code == 200
    callback = await client.post(
        f"/api/v1/payments/{payment.json()['id']}/simulate",
        headers=auth_headers(ctx.owner),
        json={"outcome": "success"},
    )
    assert callback.status_code == 409
    restored = await moderate(client, ctx, "/paid-sales/unsuspend")
    assert restored.json()["paid_sales_status"] == "pending"
    activation = await db_session.scalar(select(PaidSalesActivation))
    assert activation.status == "pending" and activation.activated_at is None
    assert (await buy(client, ctx)).status_code == 409


async def test_restore_revalidates_payout_and_preserves_suspension_on_failure(
    client, db_session, ctx
):
    await prepare(client, db_session, ctx)
    activated = await post(client, ctx, "/activate", {})
    assert (await moderate(client, ctx, "/paid-sales/suspend")).status_code == 200
    await db_session.execute(
        update(PayoutAccount)
        .where(PayoutAccount.id == activated.json()["payout_account_id"])
        .values(status="disabled")
    )
    await db_session.commit()
    response = await moderate(client, ctx, "/paid-sales/unsuspend")
    assert response.status_code == 409 and response.json()["error"]["details"]["missing"] == [
        "payout_account_active"
    ]
    assert (
        await db_session.get(Event, ctx.event_id, populate_existing=True)
    ).paid_sales_status == "suspended"


@pytest.mark.parametrize(
    "suffix", ["/suspend", "/unsuspend", "/paid-sales/suspend", "/paid-sales/unsuspend"]
)
async def test_moderation_requires_platform_admin(client, ctx, suffix):
    for user in [ctx.owner, ctx.other]:
        assert (await moderate(client, ctx, suffix, user=user)).status_code == 403
    assert (
        await client.post(f"/api/v1/admin/events/{ctx.event_id}" + suffix, json={"reason": "Fraud"})
    ).status_code == 401


async def test_moderation_reason_required_and_cancelled_events_terminal(client, db_session, ctx):
    for reason in ["", "   ", "x" * 1001]:
        result = await client.post(
            f"/api/v1/admin/events/{ctx.event_id}/suspend",
            headers=auth_headers(ctx.admin),
            json={"reason": reason},
        )
        assert result.status_code == 422
    await db_session.execute(
        update(Event).where(Event.id == ctx.event_id).values(status="cancelled")
    )
    await db_session.commit()
    assert (await moderate(client, ctx, "/suspend")).status_code == 409
    assert (await moderate(client, ctx, "/paid-sales/unsuspend")).status_code == 409


async def test_concurrent_checkout_and_suspension_have_serial_outcomes(client, db_session, ctx):
    await db_session.execute(
        update(TicketType).where(TicketType.id == ctx.ticket.id).values(price_amount=0)
    )
    await db_session.commit()
    purchased, suspended = await asyncio.gather(buy(client, ctx), moderate(client, ctx, "/suspend"))
    assert suspended.status_code == 200
    assert purchased.status_code in {201, 409}, purchased.text
    assert (await buy(client, ctx)).status_code == 409
    count = await db_session.scalar(select(func.count()).select_from(Order))
    assert count == (1 if purchased.status_code == 201 else 0)
