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
    from tests.factories import configure_seat_prices

    await configure_seat_prices(db_session, context.event_id, context.ticket_type.id)
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


async def test_seat_configuration_pricing_blocks_and_checkout_revalidation(
    client, db_session, seat_context
):
    from app.modules.organizers.models import OrganizerProfile
    from app.modules.ticketing.seat_config import SeatPrice
    from app.modules.users.models import User
    from tests.factories import create_ticket_type

    c = seat_context
    profile = await db_session.scalar(
        select(OrganizerProfile)
        .join(Event, Event.organizer_profile_id == OrganizerProfile.id)
        .where(Event.id == c.event_id)
    )
    owner = await db_session.get(User, profile.user_id)
    seat = await db_session.scalar(select(Seat).order_by(Seat.id))
    other = await create_ticket_type(
        db_session, c.event_id, name="Other category", price_amount=500
    )
    await db_session.commit()
    path = f"/api/v1/events/{c.event_id}"
    mapping = path + f"/seat-prices/{seat.price_category_id}"
    assert (
        await client.patch(
            mapping, json={"ticket_type_id": str(other.id)}, headers=auth_headers(c.buyer)
        )
    ).status_code == 404
    response = await client.patch(
        mapping, json={"ticket_type_id": str(other.id)}, headers=auth_headers(owner)
    )
    assert response.status_code == 200, response.text
    body = {"seat_ids": [str(seat.id)], "ticket_type_id": str(c.ticket_type.id)}
    assert (
        await client.post(path + "/seat-holds", json=body, headers=auth_headers(c.buyer))
    ).status_code == 409
    block = path + f"/seats/{seat.id}/block"
    assert (
        await client.patch(
            block, json={"blocked": True, "reason": "Equipment"}, headers=auth_headers(owner)
        )
    ).status_code == 204
    listing = (await client.get(path + "/seats")).json()["items"]
    selected = next(s for s in listing if s["id"] == str(seat.id))
    assert selected["status"] == "unavailable" and selected["price_amount"] == 500
    assert (
        await client.patch(
            block, json={"blocked": False, "reason": "Reopened"}, headers=auth_headers(owner)
        )
    ).status_code == 204
    body["ticket_type_id"] = str(other.id)
    result = await client.post(path + "/seat-holds", json=body, headers=auth_headers(c.buyer))
    assert result.status_code == 201, result.text
    assert (
        await client.patch(
            mapping, json={"ticket_type_id": str(c.ticket_type.id)}, headers=auth_headers(owner)
        )
    ).status_code == 409
    assert (
        await client.patch(
            block, json={"blocked": True, "reason": "Equipment"}, headers=auth_headers(owner)
        )
    ).status_code == 409
    # Stale/tampered holds must not bypass server-side category validation.
    await db_session.execute(
        update(SeatPrice)
        .where(
            SeatPrice.event_id == c.event_id, SeatPrice.price_category_id == seat.price_category_id
        )
        .values(ticket_type_id=c.ticket_type.id)
    )
    await db_session.commit()
    result = await checkout(
        client,
        c,
        data={
            "items": [
                {
                    "ticket_type_id": str(other.id),
                    "quantity": 1,
                    "seat_hold_ids": [result.json()[0]["id"]],
                }
            ]
        },
    )
    assert result.status_code == 409, result.text
    assert result.json()["error"]["code"] == "SEAT_PRICE_MISMATCH"
