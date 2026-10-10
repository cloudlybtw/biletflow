import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select, update

from app.db.settings import PlatformSetting
from app.modules.campaigns.models import Campaign
from app.modules.events.models import Event
from app.modules.notifications.models import Notification, NotificationType
from app.modules.orders.models import Attendee, Order, OrderItem, PromoRedemption
from app.modules.ticketing.models import TicketType
from app.modules.tickets.models import Ticket
from tests.factories import auth_headers, create_event, create_ticket_type, create_user
from tests.orders.conftest import add_promo
from tests.orders.helpers import cart, checkout, placed_order


async def test_free_checkout_is_atomic_and_queues_ticket_and_confirmation(
    client, db_session, context
):
    await db_session.execute(
        update(TicketType).where(TicketType.id == context.ticket_type.id).values(price_amount=0)
    )
    await db_session.commit()
    data = cart(context, quantity=2)
    data["items"][0]["attendees"] = [
        {"full_name": "Alice", "email": context.buyer.email},
        {"full_name": "Bob", "email": context.other_buyer.email},
    ]
    order = await placed_order(client, context, data=data)
    assert order["status"] == "completed" and order["total_amount"] == 0
    assert len(order["ticket_ids"]) == 2 and order["payments"] == []
    assert {a["full_name"] for a in order["items"][0]["attendees"]} == {"Alice", "Bob"}
    inventory = await db_session.get(TicketType, context.ticket_type.id, populate_existing=True)
    assert inventory.quantity_reserved == 0 and inventory.quantity_sold == 2
    notifications = (await db_session.scalars(select(Notification))).all()
    assert {n.type for n in notifications} == {
        NotificationType.ORDER_CONFIRMATION,
        NotificationType.TICKET_DELIVERY,
    }
    assert all(n.payload["order_id"] == order["id"] for n in notifications)
    assert await db_session.scalar(select(func.count()).select_from(PromoRedemption)) == 0
    tickets = (await db_session.scalars(select(Ticket))).all()
    assert all(t.qr_token.startswith("bft_") and t.ticket_code.startswith("BF-") for t in tickets)
    assert len({t.qr_token for t in tickets}) == 2
    assert (
        await client.post(f"/api/v1/orders/{order['id']}/pay", headers=auth_headers(context.buyer))
    ).status_code == 409


async def test_paid_order_uses_promo_fee_settings_and_price_snapshots(client, db_session, context):
    campaign, _ = await add_promo(db_session, context, maximum=1)
    await db_session.execute(
        update(PlatformSetting)
        .where(PlatformSetting.key == "processing_fee_percent")
        .values(value=2.5)
    )
    await db_session.execute(
        update(PlatformSetting).where(PlatformSetting.key == "order_hold_minutes").values(value=7)
    )
    await db_session.commit()
    before = datetime.now(UTC)
    order = await placed_order(
        client, context, data=cart(context, quantity=2, promo_code="checkout15")
    )
    assert order["status"] == "pending" and order["ticket_ids"] == []
    assert (
        order["subtotal_amount"],
        order["discount_amount"],
        order["fee_amount"],
        order["total_amount"],
    ) == (2000, 300, 42, 1742)
    assert datetime.fromisoformat(order["expires_at"]) >= before + timedelta(minutes=7)
    assert order["items"][0]["line_total"] == 1700
    assert await db_session.scalar(select(func.count()).select_from(Attendee)) == 2
    assert await db_session.scalar(select(func.count()).select_from(Ticket)) == 0
    assert await db_session.scalar(select(func.count()).select_from(PromoRedemption)) == 0
    campaign = await db_session.get(Campaign, campaign.id, populate_existing=True)
    assert campaign.redemption_count == 1
    ticket = await db_session.get(TicketType, context.ticket_type.id, populate_existing=True)
    assert ticket.quantity_reserved == 2 and ticket.quantity_sold == 0


async def test_full_discount_completes_immediately_but_requires_paid_activation(
    client, db_session, context
):
    campaign, _ = await add_promo(db_session, context, value=100, maximum=1)
    order = await placed_order(client, context, promo_code="CHECKOUT15")
    assert order["status"] == "completed" and order["total_amount"] == 0
    assert len(order["ticket_ids"]) == 1
    assert await db_session.scalar(select(func.count()).select_from(PromoRedemption)) == 1
    await db_session.execute(
        update(Campaign).where(Campaign.id == campaign.id).values(max_redemptions=10)
    )
    await db_session.execute(
        update(Event).where(Event.id == context.event_id).values(paid_sales_status="disabled")
    )
    await db_session.commit()
    response = await checkout(client, context, promo_code="CHECKOUT15")
    assert response.json()["error"]["code"] == "PAID_SALES_INACTIVE"


async def test_discount_is_allocated_across_only_eligible_lines(client, db_session, context):
    await db_session.execute(
        update(TicketType).where(TicketType.id == context.ticket_type.id).values(price_amount=101)
    )
    other = await create_ticket_type(db_session, context.event_id, price_amount=2000)
    await db_session.commit()
    await add_promo(db_session, context, types=[context.ticket_type.id])
    data = {
        "promo_code": "CHECKOUT15",
        "items": [
            {"ticket_type_id": str(context.ticket_type.id), "quantity": 3},
            {"ticket_type_id": str(other.id), "quantity": 1},
        ],
    }
    order = await placed_order(client, context, data=data)
    assert (order["subtotal_amount"], order["discount_amount"], order["total_amount"]) == (
        2303,
        45,
        2258,
    )
    lines = {line["ticket_type_id"]: line for line in order["items"]}
    assert lines[str(context.ticket_type.id)]["discount_amount"] == 45
    assert lines[str(other.id)]["discount_amount"] == 0
    assert sum(line["line_total"] for line in order["items"]) == order["total_amount"]


async def test_rounding_to_zero_does_not_claim_a_promo(client, db_session, context):
    await db_session.execute(
        update(TicketType).where(TicketType.id == context.ticket_type.id).values(price_amount=1)
    )
    await db_session.commit()
    campaign, _ = await add_promo(db_session, context, value=1, maximum=1)
    order = await placed_order(client, context, promo_code="CHECKOUT15")
    assert order["discount_amount"] == 0 and order["total_amount"] == 1
    assert (
        await db_session.get(Campaign, campaign.id, populate_existing=True)
    ).redemption_count == 0


@pytest.mark.parametrize(
    "target,values,error",
    [
        ("event", {"status": "draft"}, "EVENT_NOT_PUBLISHED"),
        ("event", {"status": "cancelled"}, "EVENT_NOT_PUBLISHED"),
        ("event", {"status": "unpublished"}, "EVENT_NOT_PUBLISHED"),
        ("event", {"paid_sales_status": "disabled"}, "PAID_SALES_INACTIVE"),
        ("event", {"paid_sales_status": "pending"}, "PAID_SALES_INACTIVE"),
        ("event", {"paid_sales_status": "suspended"}, "PAID_SALES_INACTIVE"),
        ("ticket", {"is_hidden": True}, "TICKET_TYPE_UNAVAILABLE"),
        ("ticket", {"quantity_total": 0}, "SOLD_OUT"),
        ("ticket", {"min_per_order": 2}, "ORDER_LIMIT_EXCEEDED"),
    ],
)
async def test_checkout_business_guards(client, db_session, context, target, values, error):
    model = Event if target == "event" else TicketType
    identifier = context.event_id if target == "event" else context.ticket_type.id
    await db_session.execute(update(model).where(model.id == identifier).values(**values))
    await db_session.commit()
    response = await checkout(client, context)
    assert response.status_code in (400, 409), response.text
    assert response.json()["error"]["code"] == error
    assert await db_session.scalar(select(func.count()).select_from(Order)) == 0


@pytest.mark.parametrize(
    "target,field,offset,error",
    [
        ("event", "registration_opens_at", 1, "REGISTRATION_NOT_OPEN"),
        ("event", "registration_closes_at", 0, "REGISTRATION_CLOSED"),
        ("ticket", "sales_start_at", 1, "TICKET_SALES_NOT_OPEN"),
        ("ticket", "sales_end_at", 0, "TICKET_SALES_CLOSED"),
        ("event", "registration_opens_at", 0, None),
        ("ticket", "sales_start_at", 0, None),
    ],
)
async def test_window_boundaries(
    client, db_session, context, monkeypatch, target, field, offset, error
):
    fixed = datetime.now(UTC)
    monkeypatch.setattr("app.modules.orders.service.now_utc", lambda: fixed)
    model = Event if target == "event" else TicketType
    identifier = context.event_id if target == "event" else context.ticket_type.id
    await db_session.execute(
        update(model)
        .where(model.id == identifier)
        .values(**{field: fixed + timedelta(seconds=offset)})
    )
    await db_session.commit()
    response = await checkout(client, context)
    assert response.status_code == (409 if error else 201), response.text
    if error:
        assert response.json()["error"]["code"] == error


async def test_checkout_requires_verified_account_and_hides_private_events(
    client, db_session, context
):
    user = await create_user(db_session)
    await db_session.commit()
    path = f"/api/v1/events/{context.event_id}/orders"
    assert (await client.post(path, json=cart(context))).status_code == 401
    assert (
        await client.post(path, json=cart(context), headers=auth_headers(user))
    ).status_code == 403
    await db_session.execute(
        update(Event).where(Event.id == context.event_id).values(visibility="private")
    )
    await db_session.commit()
    assert (await checkout(client, context)).status_code == 404
    await db_session.execute(
        update(Event).where(Event.id == context.event_id).values(visibility="unlisted")
    )
    await db_session.commit()
    assert (await checkout(client, context)).status_code == 201


async def test_invalid_cart_cannot_reserve_partial_inventory_or_claim_promo(
    client, db_session, context
):
    campaign, _ = await add_promo(db_session, context)
    foreign_event = await create_event(db_session)
    foreign_type = await create_ticket_type(db_session, foreign_event)
    await db_session.commit()
    data = cart(context, promo_code="CHECKOUT15")
    data["items"].append({"ticket_type_id": str(foreign_type.id), "quantity": 1})
    response = await checkout(client, context, data=data)
    assert response.json()["error"]["code"] == "TICKET_TYPE_UNAVAILABLE"
    assert await db_session.scalar(select(func.count()).select_from(Order)) == 0
    assert (
        await db_session.get(Campaign, campaign.id, populate_existing=True)
    ).redemption_count == 0
    assert (
        await db_session.get(TicketType, context.ticket_type.id, populate_existing=True)
    ).quantity_reserved == 0


async def test_failure_during_free_issuance_rolls_back_everything(
    client, db_session, context, monkeypatch
):
    campaign, _ = await add_promo(db_session, context, value=100)

    async def fail_enqueue(*args, **kwargs):
        raise RuntimeError("Forced outbox failure")

    monkeypatch.setattr("app.modules.orders.service.notifications.enqueue", fail_enqueue)
    response = await checkout(client, context, promo_code="CHECKOUT15")
    assert response.status_code == 500
    for model in [Order, OrderItem, Attendee, Ticket, PromoRedemption, Notification]:
        assert await db_session.scalar(select(func.count()).select_from(model)) == 0
    assert (
        await db_session.get(Campaign, campaign.id, populate_existing=True)
    ).redemption_count == 0
    ticket = await db_session.get(TicketType, context.ticket_type.id, populate_existing=True)
    assert ticket.quantity_sold == ticket.quantity_reserved == 0


@pytest.mark.parametrize(
    "key,value",
    [
        ("order_hold_minutes", 0),
        ("order_hold_minutes", 1.5),
        ("processing_fee_percent", -1),
        ("processing_fee_percent", 101),
        ("processing_fee_percent", True),
        ("processing_fee_percent", "NaN"),
    ],
)
async def test_invalid_platform_settings_block_checkout(client, db_session, context, key, value):
    await db_session.execute(
        update(PlatformSetting).where(PlatformSetting.key == key).values(value=value)
    )
    await db_session.commit()
    response = await checkout(client, context)
    assert response.status_code == 503, response.text
    assert response.json()["error"]["code"] == "INVALID_CHECKOUT_SETTINGS"
    assert await db_session.scalar(select(func.count()).select_from(Order)) == 0


@pytest.mark.parametrize(
    "changes",
    [
        {"quantity": 0},
        {"quantity": -1},
        {"attendees": []},
        {"attendees": [{"full_name": "  "}]},
        {"seat_hold_ids": [str(uuid.uuid4()), str(uuid.uuid4())]},
        {"price_amount": 1},
    ],
)
async def test_invalid_request_shape(client, context, changes):
    data = cart(context)
    data["items"][0].update(changes)
    assert (await checkout(client, context, data=data)).status_code == 422


async def test_duplicate_lines_and_client_supplied_totals_are_rejected(client, context):
    data = cart(context)
    data["items"] *= 2
    assert (await checkout(client, context, data=data)).status_code == 422
    assert (await checkout(client, context, data=cart(context, total_amount=1))).status_code == 422


async def test_ended_or_deleted_events_cannot_sell(client, db_session, context):
    now = datetime.now(UTC)
    await db_session.execute(
        update(Event)
        .where(Event.id == context.event_id)
        .values(starts_at=now - timedelta(hours=2), ends_at=now - timedelta(hours=1))
    )
    await db_session.commit()
    assert (await checkout(client, context)).json()["error"]["code"] == "EVENT_ENDED"
    await db_session.execute(
        update(Event).where(Event.id == context.event_id).values(deleted_at=now)
    )
    await db_session.commit()
    assert (await checkout(client, context)).status_code == 404


async def test_overflow_after_promo_claim_rolls_back_the_claim(client, db_session, context):
    from app.modules.orders.pricing import MAX_AMOUNT

    campaign, _ = await add_promo(db_session, context, value=1)
    await db_session.execute(
        update(TicketType)
        .where(TicketType.id == context.ticket_type.id)
        .values(price_amount=MAX_AMOUNT)
    )
    await db_session.execute(
        update(PlatformSetting)
        .where(PlatformSetting.key == "processing_fee_percent")
        .values(value=100)
    )
    await db_session.commit()
    response = await checkout(client, context, promo_code="CHECKOUT15")
    assert (
        response.status_code == 422 and response.json()["error"]["code"] == "CART_TOTAL_TOO_LARGE"
    )
    assert (
        await db_session.get(Campaign, campaign.id, populate_existing=True)
    ).redemption_count == 0
    assert await db_session.scalar(select(func.count()).select_from(Order)) == 0
