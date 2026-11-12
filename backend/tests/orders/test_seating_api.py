import asyncio
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select, update

from app.modules.events.models import Event
from app.modules.ticketing.holds import SeatHold
from app.modules.ticketing.models import TicketType
from app.modules.venues.models import Seat
from tests.factories import auth_headers
from tests.orders.helpers import checkout


@pytest.fixture
async def seat_context(db_session, context):
    await db_session.execute(
        update(Event)
        .where(Event.id == context.event_id)
        .values(venue_id=uuid.UUID("20000000-0000-0000-0000-000000000001"), seating_mode="assigned")
    )
    await db_session.execute(
        update(TicketType).where(TicketType.id == context.ticket_type.id).values(price_amount=0)
    )
    await db_session.commit()
    return context


async def test_hold_race_is_atomic_private_and_can_be_released(client, db_session, seat_context):
    c = seat_context
    seat = await db_session.scalar(select(Seat.id).order_by(Seat.id))
    path = f"/api/v1/events/{c.event_id}"
    body = {"seat_ids": [str(seat)], "ticket_type_id": str(c.ticket_type.id)}
    results = await asyncio.gather(
        *(
            client.post(path + "/seat-holds", json=body, headers=auth_headers(user))
            for user in [c.buyer, c.other_buyer]
        )
    )
    assert sorted(r.status_code for r in results) == [201, 409]
    winner = next(index for index, r in enumerate(results) if r.status_code == 201)
    owner = [c.buyer, c.other_buyer][winner]
    stranger = [c.buyer, c.other_buyer][1 - winner]
    hold = results[winner].json()[0]
    listing = await client.get(path + "/seats", headers=auth_headers(owner))
    state = next(item for item in listing.json()["items"] if item["id"] == str(seat))
    assert state["status"] == "held" and state["held_by_me"] is True
    assert "held_by_user_id" not in state
    assert (
        await client.delete(path + f"/seat-holds/{hold['id']}", headers=auth_headers(stranger))
    ).status_code == 404
    assert (
        await client.delete(path + f"/seat-holds/{hold['id']}", headers=auth_headers(owner))
    ).status_code == 204
    assert (
        await client.post(path + "/seat-holds", json=body, headers=auth_headers(stranger))
    ).status_code == 201


async def test_hold_checkout_sells_seat_and_cannot_release_order_hold(
    client, db_session, seat_context
):
    c = seat_context
    seat = await db_session.scalar(select(Seat.id).order_by(Seat.id))
    path = f"/api/v1/events/{c.event_id}"
    hold = (
        await client.post(
            path + "/seat-holds",
            json={"seat_ids": [str(seat)], "ticket_type_id": str(c.ticket_type.id)},
            headers=auth_headers(c.buyer),
        )
    ).json()[0]
    result = await checkout(
        client,
        c,
        data={
            "items": [
                {
                    "ticket_type_id": str(c.ticket_type.id),
                    "quantity": 1,
                    "seat_hold_ids": [hold["id"]],
                }
            ]
        },
    )
    assert result.status_code == 201, result.text
    assert result.json()["status"] == "completed"
    listing = (await client.get(path + "/seats")).json()
    assert next(s for s in listing["items"] if s["id"] == str(seat))["status"] == "sold"
    assert (
        await client.delete(path + f"/seat-holds/{hold['id']}", headers=auth_headers(c.buyer))
    ).status_code == 409
    assert (
        await client.post(
            path + "/seat-holds",
            json={"seat_ids": [str(seat)], "ticket_type_id": str(c.ticket_type.id)},
            headers=auth_headers(c.other_buyer),
        )
    ).status_code == 409


async def test_expired_holds_are_reclaimed_and_duplicate_input_rejected(
    client, db_session, seat_context
):
    c = seat_context
    seat = await db_session.scalar(select(Seat.id).order_by(Seat.id))
    path = f"/api/v1/events/{c.event_id}/seat-holds"
    body = {"seat_ids": [str(seat)], "ticket_type_id": str(c.ticket_type.id)}
    first = await client.post(path, json=body, headers=auth_headers(c.buyer))
    await db_session.execute(
        update(SeatHold)
        .where(SeatHold.id == uuid.UUID(first.json()[0]["id"]))
        .values(expires_at=datetime.now(UTC) - timedelta(seconds=1))
    )
    await db_session.commit()
    assert (
        await client.post(path, json=body, headers=auth_headers(c.other_buyer))
    ).status_code == 201
    assert (
        await client.post(
            path, json={**body, "seat_ids": [str(seat), str(seat)]}, headers=auth_headers(c.buyer)
        )
    ).status_code == 422
    assert (await client.post(path, json=body)).status_code == 401
