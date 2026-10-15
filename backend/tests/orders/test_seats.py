import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select, update

from app.modules.events.models import Event
from app.modules.orders.models import Order
from app.modules.orders.service import sweep_expired
from app.modules.ticketing.holds import SeatHold
from app.modules.ticketing.models import TicketType
from app.modules.venues.models import Seat, VenueRow
from tests.factories import auth_headers
from tests.orders.helpers import cart, checkout, placed_order
from tests.orders.test_expiry import make_expired


@pytest.fixture
async def seated(db_session, context):
    venue = uuid.UUID("20000000-0000-0000-0000-000000000001")
    await db_session.execute(
        update(Event)
        .where(Event.id == context.event_id)
        .values(venue_id=venue, seating_mode="assigned")
    )
    seats = (
        await db_session.scalars(
            select(Seat)
            .join(VenueRow, VenueRow.id == Seat.row_id)
            .where(VenueRow.label == "A")
            .order_by(Seat.position_x)
            .limit(2)
        )
    ).all()
    holds = [
        SeatHold(
            event_id=context.event_id,
            seat_id=seat.id,
            ticket_type_id=context.ticket_type.id,
            held_by_user_id=context.buyer.id,
            session_token="test-seat-session",
            expires_at=datetime.now(UTC) + timedelta(minutes=10),
        )
        for seat in seats
    ]
    db_session.add_all(holds)
    await db_session.commit()
    return holds


def seated_cart(context, holds):
    data = cart(context, quantity=len(holds))
    data["items"][0]["seat_hold_ids"] = [str(hold.id) for hold in holds]
    data["items"][0]["attendees"] = [{"full_name": f"Guest {i + 1}"} for i, _ in enumerate(holds)]
    return data


async def test_sweeper_expires_unattached_holds_and_retains_live_holds(db_session, seated):
    await db_session.execute(
        update(SeatHold)
        .where(SeatHold.id == seated[0].id)
        .values(expires_at=datetime.now(UTC) - timedelta(seconds=1))
    )
    await db_session.commit()
    assert await sweep_expired(db_session) == 0
    assert (
        await db_session.get(SeatHold, seated[0].id, populate_existing=True)
    ).status == "expired"
    assert (await db_session.get(SeatHold, seated[1].id, populate_existing=True)).status == "active"


async def test_owned_seat_holds_attach_and_issue_snapshot_labels(
    client, db_session, context, seated
):
    await db_session.execute(
        update(TicketType).where(TicketType.id == context.ticket_type.id).values(price_amount=0)
    )
    await db_session.commit()
    order = await placed_order(client, context, data=seated_cart(context, seated))
    assert order["status"] == "completed" and len(order["items"]) == 2
    for index, hold in enumerate(seated):
        refreshed = await db_session.get(SeatHold, hold.id, populate_existing=True)
        assert refreshed.status == "converted" and str(refreshed.order_id) == order["id"]
        assert refreshed.expires_at == datetime.fromisoformat(order["expires_at"])
        listing = (await client.get("/api/v1/tickets", headers=auth_headers(context.buyer))).json()
        ticket = next(t for t in listing["items"] if t["seat_id"] == str(hold.seat_id))
        assert ticket["seat_section_label"] == "Main"
        assert ticket["seat_row_label"] == "A"
        assert ticket["seat_number_label"] == str(index + 1)
        assert ticket["attendee_name"] == f"Guest {index + 1}"


async def test_expiry_releases_attached_seat_holds(client, db_session, context, seated):
    order = await placed_order(client, context, data=seated_cart(context, seated))
    await make_expired(db_session, order)
    expired = await client.get(f"/api/v1/orders/{order['id']}", headers=auth_headers(context.buyer))
    assert expired.json()["status"] == "expired"
    for hold in seated:
        assert (await db_session.get(SeatHold, hold.id, populate_existing=True)).status == "expired"


@pytest.mark.parametrize("reason", ["expired", "foreign_owner", "released", "wrong_type"])
async def test_invalid_holds_cannot_create_orders(client, db_session, context, seated, reason):
    values = (
        {"expires_at": datetime.now(UTC) - timedelta(seconds=1)}
        if reason == "expired"
        else {"held_by_user_id": context.other_buyer.id}
        if reason == "foreign_owner"
        else {"status": "released"}
        if reason == "released"
        else {"ticket_type_id": uuid.uuid4()}
    )
    if reason == "wrong_type":
        from tests.factories import create_ticket_type

        foreign = await create_ticket_type(db_session, context.event_id)
        values = {"ticket_type_id": foreign.id}
    await db_session.execute(update(SeatHold).where(SeatHold.id == seated[0].id).values(**values))
    await db_session.commit()
    response = await checkout(client, context, data=seated_cart(context, seated))
    assert response.status_code == 409, response.text
    assert response.json()["error"]["code"] == "INVALID_SEAT_HOLD"
    assert (await db_session.scalars(select(Order))).first() is None


async def test_missing_and_duplicate_holds_are_rejected(client, context, seated):
    assert (await checkout(client, context)).json()["error"]["code"] == "ASSIGNED_SEATS_REQUIRED"
    data = seated_cart(context, seated)
    data["items"][0]["seat_hold_ids"] = [str(seated[0].id)] * 2
    assert (await checkout(client, context, data=data)).status_code == 422
