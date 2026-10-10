import asyncio
import uuid

from sqlalchemy import func, select, update

from app.modules.campaigns.models import Campaign
from app.modules.events.models import Event
from app.modules.notifications.models import Notification, NotificationType
from app.modules.orders.models import PromoRedemption
from app.modules.payments.models import Payment
from app.modules.ticketing.models import TicketType
from app.modules.tickets.models import Ticket
from tests.factories import auth_headers
from tests.orders.conftest import add_promo
from tests.orders.helpers import pay, placed_order, simulate


async def test_success_issues_tickets_once_and_confirms_claim(client, db_session, context):
    campaign, _ = await add_promo(db_session, context, maximum=1)
    order = await placed_order(client, context, quantity=2, promo_code="CHECKOUT15")
    payment = await pay(client, context, order["id"])
    assert payment["status"] == "initiated" and payment["amount"] == 1700
    responses = await asyncio.gather(*[simulate(client, context, payment["id"]) for _ in range(5)])
    assert all(response.status_code == 200 for response in responses), [r.text for r in responses]
    assert all(response.json()["status"] == "succeeded" for response in responses)
    assert await db_session.scalar(select(func.count()).select_from(Ticket)) == 2
    assert await db_session.scalar(select(func.count()).select_from(PromoRedemption)) == 1
    assert await db_session.scalar(select(func.count()).select_from(Notification)) == 2
    assert (
        await db_session.get(Campaign, campaign.id, populate_existing=True)
    ).redemption_count == 1
    ticket = await db_session.get(TicketType, context.ticket_type.id, populate_existing=True)
    assert ticket.quantity_sold == 2 and ticket.quantity_reserved == 0
    detail = (
        await client.get(f"/api/v1/orders/{order['id']}", headers=auth_headers(context.buyer))
    ).json()
    assert detail["status"] == "completed" and len(detail["ticket_ids"]) == 2
    assert (await simulate(client, context, payment["id"], "failure")).status_code == 409


async def test_repeated_pay_reuses_live_attempt_failure_allows_retry(client, db_session, context):
    campaign, _ = await add_promo(db_session, context, maximum=1)
    order = await placed_order(client, context, promo_code="CHECKOUT15")
    responses = await asyncio.gather(
        *[
            client.post(f"/api/v1/orders/{order['id']}/pay", headers=auth_headers(context.buyer))
            for _ in range(5)
        ]
    )
    assert all(response.status_code == 201 for response in responses)
    assert len({response.json()["id"] for response in responses}) == 1
    first = responses[0].json()
    failure = await simulate(client, context, first["id"], "failure")
    assert failure.status_code == 200 and failure.json()["status"] == "failed"
    assert (await simulate(client, context, first["id"], "failure")).status_code == 200
    assert (await simulate(client, context, first["id"])).status_code == 409
    assert (
        await db_session.scalar(
            select(func.count())
            .select_from(Notification)
            .where(Notification.type == NotificationType.PAYMENT_FAILED)
        )
        == 1
    )
    pending = (
        await client.get(f"/api/v1/orders/{order['id']}", headers=auth_headers(context.buyer))
    ).json()
    assert pending["expires_at"] == order["expires_at"] and pending["status"] == "awaiting_payment"
    assert (
        await db_session.get(Campaign, campaign.id, populate_existing=True)
    ).redemption_count == 1
    assert (
        await db_session.get(TicketType, context.ticket_type.id, populate_existing=True)
    ).quantity_reserved == 1
    second = await pay(client, context, order["id"])
    assert second["id"] != first["id"]
    assert (await simulate(client, context, second["id"])).status_code == 200
    assert await db_session.scalar(select(func.count()).select_from(Payment)) == 2
    assert await db_session.scalar(select(func.count()).select_from(Ticket)) == 1


async def test_snapshot_prices_and_reserved_discount_survive_configuration_changes(
    client, db_session, context
):
    campaign, _ = await add_promo(db_session, context, maximum=1)
    order = await placed_order(client, context, promo_code="CHECKOUT15")
    payment = await pay(client, context, order["id"])
    await db_session.execute(
        update(TicketType)
        .where(TicketType.id == context.ticket_type.id)
        .values(price_amount=9000, is_hidden=True)
    )
    await db_session.execute(
        update(Campaign)
        .where(Campaign.id == campaign.id)
        .values(status="disabled", discount_value=1)
    )
    await db_session.commit()
    success = await simulate(client, context, payment["id"])
    assert success.status_code == 200, success.text
    assert success.json()["amount"] == 850
    redemption = await db_session.scalar(select(PromoRedemption))
    assert redemption.discount_amount == 150


async def test_moderation_blocks_payment_without_issuing_tickets(client, db_session, context):
    order = await placed_order(client, context)
    payment = await pay(client, context, order["id"])
    await db_session.execute(
        update(Event).where(Event.id == context.event_id).values(paid_sales_status="suspended")
    )
    await db_session.commit()
    suspended = await simulate(client, context, payment["id"])
    assert (
        suspended.status_code == 409 and suspended.json()["error"]["code"] == "PAID_SALES_INACTIVE"
    )
    assert await db_session.scalar(select(func.count()).select_from(Ticket)) == 0
    assert (
        await db_session.get(Payment, uuid.UUID(payment["id"]), populate_existing=True)
    ).status == "initiated"
    await db_session.execute(
        update(Event)
        .where(Event.id == context.event_id)
        .values(paid_sales_status="active", status="unpublished")
    )
    await db_session.commit()
    assert (await simulate(client, context, payment["id"])).json()["error"][
        "code"
    ] == "EVENT_NOT_ACCEPTING_PAYMENTS"


async def test_payment_simulation_rejects_real_provider_or_wrong_amount(
    client, db_session, context
):
    order = await placed_order(client, context)
    payment = await pay(client, context, order["id"])
    await db_session.execute(
        update(Payment).where(Payment.id == uuid.UUID(payment["id"])).values(is_simulated=False)
    )
    await db_session.commit()
    assert (await simulate(client, context, payment["id"])).json()["error"][
        "code"
    ] == "PAYMENT_NOT_SIMULATED"
    await db_session.execute(
        update(Payment)
        .where(Payment.id == uuid.UUID(payment["id"]))
        .values(is_simulated=True, amount=1)
    )
    await db_session.commit()
    assert (await simulate(client, context, payment["id"])).json()["error"][
        "code"
    ] == "PAYMENT_AMOUNT_MISMATCH"
    assert await db_session.scalar(select(func.count()).select_from(Ticket)) == 0


async def test_invalid_outcome_and_other_buyer_cannot_simulate(client, context):
    order = await placed_order(client, context)
    payment = await pay(client, context, order["id"])
    path = f"/api/v1/payments/{payment['id']}/simulate"
    assert (await client.post(path, json={"outcome": "success"})).status_code == 401
    assert (
        await client.post(
            path, json={"outcome": "success"}, headers=auth_headers(context.other_buyer)
        )
    ).status_code == 404
    assert (
        await client.post(path, json={"outcome": "succeeded"}, headers=auth_headers(context.buyer))
    ).status_code == 422
    assert (
        await client.post(
            path, json={"outcome": "success", "amount": 1}, headers=auth_headers(context.buyer)
        )
    ).status_code == 422
