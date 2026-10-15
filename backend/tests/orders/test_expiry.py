import asyncio
import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, call

import pytest
from sqlalchemy import func, select, update

from app.jobs import expire_orders
from app.main import create_app
from app.modules.campaigns.models import Campaign
from app.modules.orders.models import Order, PromoRedemption
from app.modules.orders.service import sweep_expired
from app.modules.payments.models import Payment
from app.modules.ticketing.models import TicketType
from app.modules.tickets.models import Ticket
from tests.factories import auth_headers
from tests.orders.conftest import add_promo
from tests.orders.helpers import cart, checkout, pay, placed_order, simulate


async def make_expired(db_session, order):
    await db_session.execute(
        update(Order)
        .where(Order.id == uuid.UUID(order["id"]))
        .values(expires_at=datetime.now(UTC) - timedelta(seconds=1))
    )
    await db_session.commit()


async def test_sweeper_releases_inventory_claim_and_cancels_payment_once(
    client, db_session, context
):
    campaign, _ = await add_promo(db_session, context, maximum=1)
    order = await placed_order(client, context, promo_code="CHECKOUT15")
    assert await db_session.scalar(select(func.count()).select_from(PromoRedemption)) == 1
    payment = await pay(client, context, order["id"])
    await make_expired(db_session, order)
    assert await sweep_expired(db_session) == 1
    assert await sweep_expired(db_session) == 0
    assert await db_session.scalar(select(func.count()).select_from(PromoRedemption)) == 0
    assert (
        await db_session.get(Campaign, campaign.id, populate_existing=True)
    ).redemption_count == 0
    assert (
        await db_session.get(TicketType, context.ticket_type.id, populate_existing=True)
    ).quantity_reserved == 0
    assert (
        await db_session.get(Payment, uuid.UUID(payment["id"]), populate_existing=True)
    ).status == "cancelled"
    assert (
        await db_session.get(Order, uuid.UUID(order["id"]), populate_existing=True)
    ).status == "expired"
    late = await simulate(client, context, payment["id"])
    assert late.status_code == 409 and late.json()["error"]["code"] == "ORDER_EXPIRED"
    assert await db_session.scalar(select(func.count()).select_from(Ticket)) == 0
    next_order = await placed_order(
        client, context, buyer=context.other_buyer, promo_code="CHECKOUT15"
    )
    assert next_order["status"] == "pending"
    assert (
        await db_session.get(Campaign, campaign.id, populate_existing=True)
    ).redemption_count == 1


async def test_order_detail_lazily_expires(client, db_session, context):
    order = await placed_order(client, context)
    await make_expired(db_session, order)
    detail = await client.get(f"/api/v1/orders/{order['id']}", headers=auth_headers(context.buyer))
    assert detail.status_code == 200 and detail.json()["status"] == "expired"
    assert (
        await db_session.get(TicketType, context.ticket_type.id, populate_existing=True)
    ).quantity_reserved == 0


async def test_my_orders_lazily_expire_and_keep_other_buyers_private(client, db_session, context):
    order = await placed_order(client, context)
    await make_expired(db_session, order)
    listing = await client.get("/api/v1/orders", headers=auth_headers(context.buyer))
    assert listing.json()["items"][0]["status"] == "expired"
    assert (await client.get("/api/v1/orders", headers=auth_headers(context.other_buyer))).json()[
        "total"
    ] == 0


async def test_checkout_persists_lazy_cleanup_even_if_new_cart_fails(client, db_session, context):
    campaign, _ = await add_promo(db_session, context, maximum=1)
    order = await placed_order(client, context, promo_code="CHECKOUT15")
    await make_expired(db_session, order)
    data = cart(context)
    data["items"][0]["ticket_type_id"] = str(uuid.uuid4())
    invalid = await checkout(client, context, buyer=context.other_buyer, data=data)
    assert invalid.status_code == 400
    assert (
        await db_session.get(Order, uuid.UUID(order["id"]), populate_existing=True)
    ).status == "expired"
    assert (
        await db_session.get(Campaign, campaign.id, populate_existing=True)
    ).redemption_count == 0
    assert (
        await db_session.get(TicketType, context.ticket_type.id, populate_existing=True)
    ).quantity_reserved == 0


async def test_pay_after_deadline_persists_expiry_before_returning_error(
    client, db_session, context
):
    order = await placed_order(client, context)
    await make_expired(db_session, order)
    response = await client.post(
        f"/api/v1/orders/{order['id']}/pay", headers=auth_headers(context.buyer)
    )
    assert response.status_code == 409 and response.json()["error"]["code"] == "ORDER_EXPIRED"
    assert (
        await db_session.get(Order, uuid.UUID(order["id"]), populate_existing=True)
    ).status == "expired"


async def test_sweepers_and_late_success_never_issue_expired_tickets(
    client, db_session, test_sessionmaker, context
):
    campaign, _ = await add_promo(db_session, context, maximum=1)
    order = await placed_order(client, context, promo_code="CHECKOUT15")
    payment = await pay(client, context, order["id"])
    await make_expired(db_session, order)

    async def sweep():
        async with test_sessionmaker() as session:
            return await sweep_expired(session)

    responses = await asyncio.gather(sweep(), sweep(), simulate(client, context, payment["id"]))
    assert responses[-1].status_code == 409
    assert sum(responses[:2]) in (0, 1)  # Lazy payment expiry may win instead.
    assert (
        await db_session.get(Order, uuid.UUID(order["id"]), populate_existing=True)
    ).status == "expired"
    assert (
        await db_session.get(Campaign, campaign.id, populate_existing=True)
    ).redemption_count == 0
    assert (
        await db_session.get(TicketType, context.ticket_type.id, populate_existing=True)
    ).quantity_reserved == 0
    assert await db_session.scalar(select(func.count()).select_from(Ticket)) == 0


async def test_api_lifespan_expires_orders_without_requests_and_stops_task(
    client, db_session, test_sessionmaker, context, monkeypatch
):
    await add_promo(db_session, context)
    order = await placed_order(client, context, promo_code="CHECKOUT15")
    await make_expired(db_session, order)
    swept = asyncio.Event()
    real_sweep = expire_orders.sweep_expired

    async def sweep(session):
        result = await real_sweep(session)
        swept.set()
        return result

    monkeypatch.setattr(expire_orders, "sweep_expired", sweep)
    app = create_app(session_factory=test_sessionmaker)
    async with app.router.lifespan_context(app):
        task = app.state.background_task
        await asyncio.wait_for(swept.wait(), timeout=5)
        assert not task.done()
        assert (
            await db_session.get(Order, uuid.UUID(order["id"]), populate_existing=True)
        ).status == "expired"
        assert await db_session.scalar(select(func.count()).select_from(PromoRedemption)) == 0
        assert (
            await db_session.get(TicketType, context.ticket_type.id, populate_existing=True)
        ).quantity_reserved == 0
    assert task.cancelled()


async def test_expiry_task_retries_failure_at_thirty_second_intervals(
    test_sessionmaker, monkeypatch
):
    sweep = AsyncMock(side_effect=[RuntimeError("database temporarily unavailable"), 0])
    sleep = AsyncMock(side_effect=[None, asyncio.CancelledError()])
    monkeypatch.setattr(expire_orders, "sweep_expired", sweep)
    monkeypatch.setattr(expire_orders, "asyncio", SimpleNamespace(sleep=sleep))
    with pytest.raises(asyncio.CancelledError):
        await expire_orders.run(once=False, interval_seconds=30, session_factory=test_sessionmaker)
    assert sweep.await_count == 2
    assert sleep.await_args_list == [call(30), call(30)]
