import uuid

from app.modules.venues.models import Venue
from tests.factories import auth_headers, create_organizer, create_user, create_verified_user

PLACE = {
    "name": "Nazarbayev University",
    "address_line": "53 Kabanbay Batyr Ave",
    "city": "Astana",
    "latitude": "51.0905671234",
    "longitude": "71.3981234567",
}


async def test_create_venue_requires_verified_organizer(client, db_session):
    assert (await client.post("/api/v1/venues", json=PLACE)).status_code == 401
    unverified = await create_user(db_session)
    await create_organizer(db_session, unverified)
    no_profile = await create_verified_user(db_session)
    await db_session.commit()
    headers = auth_headers(unverified)
    assert (await client.post("/api/v1/venues", json=PLACE, headers=headers)).status_code == 403
    headers = auth_headers(no_profile)
    assert (await client.post("/api/v1/venues", json=PLACE, headers=headers)).status_code == 404


async def test_organizer_creates_reusable_custom_venue(client, db_session):
    user = await create_verified_user(db_session)
    await create_organizer(db_session, user)
    await db_session.commit()
    headers = auth_headers(user)

    response = await client.post("/api/v1/venues", json=PLACE, headers=headers)
    assert response.status_code == 201, response.text
    venue = response.json()
    assert venue["is_predefined"] is False
    assert venue["country"] == "KZ"
    assert venue["latitude"] == "51.090567"
    assert venue["longitude"] == "71.398123"

    again = await client.post("/api/v1/venues", json=PLACE, headers=headers)
    assert again.status_code == 201
    assert again.json()["id"] == venue["id"]
    row = await db_session.get(Venue, uuid.UUID(venue["id"]))
    assert row.created_by == user.id

    detail = (await client.get(f"/api/v1/venues/{venue['id']}")).json()
    assert detail["address_line"] == PLACE["address_line"]
    assert detail["sections"] == []


async def test_venue_payload_validation(client, db_session):
    user = await create_verified_user(db_session)
    await create_organizer(db_session, user)
    await db_session.commit()
    headers = auth_headers(user)
    for bad in (
        {**PLACE, "name": "   "},
        {**PLACE, "latitude": 91},
        {**PLACE, "longitude": -181},
        {**PLACE, "timezone": "Mars/Base"},
        {**PLACE, "sections": []},
    ):
        response = await client.post("/api/v1/venues", json=bad, headers=headers)
        assert response.status_code == 422, bad
