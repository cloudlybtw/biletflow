import asyncio

import pytest
from sqlalchemy import func, select, update

from app.modules.campaigns.models import Campaign
from app.modules.orders.models import Order
from app.modules.ticketing.models import TicketType
from app.modules.tickets.models import Ticket
from tests.orders.conftest import add_promo
from tests.orders.helpers import checkout


@pytest.mark.parametrize("price", [0, 1000])
async def test_last_ticket_race_has_exactly_one_buyer(client, db_session, context, price):
    await db_session.execute(
        update(TicketType)
        .where(TicketType.id == context.ticket_type.id)
        .values(price_amount=price, quantity_total=1)
    )
    await db_session.commit()
    results = await asyncio.gather(
        checkout(client, context), checkout(client, context, buyer=context.other_buyer)
    )
    assert sorted(r.status_code for r in results) == [201, 409], [r.text for r in results]
    failed = next(r for r in results if r.status_code == 409)
    assert failed.json()["error"]["code"] == "SOLD_OUT"
    assert await db_session.scalar(select(func.count()).select_from(Order)) == 1
    ticket = await db_session.get(TicketType, context.ticket_type.id, populate_existing=True)
    assert ticket.quantity_sold + ticket.quantity_reserved == 1
    assert await db_session.scalar(select(func.count()).select_from(Ticket)) == (
        1 if price == 0 else 0
    )


async def test_last_promo_claim_race_has_exactly_one_claim(client, db_session, context):
    campaign, _ = await add_promo(db_session, context, maximum=1)
    results = await asyncio.gather(
        checkout(client, context, promo_code="CHECKOUT15"),
        checkout(client, context, buyer=context.other_buyer, promo_code="CHECKOUT15"),
    )
    assert sorted(r.status_code for r in results) == [201, 400], [r.text for r in results]
    failed = next(r for r in results if r.status_code == 400)
    assert failed.json()["error"]["code"] == "PROMO_EXHAUSTED"
    assert await db_session.scalar(select(func.count()).select_from(Order)) == 1
    assert (
        await db_session.get(Campaign, campaign.id, populate_existing=True)
    ).redemption_count == 1
    assert (
        await db_session.get(TicketType, context.ticket_type.id, populate_existing=True)
    ).quantity_reserved == 1
