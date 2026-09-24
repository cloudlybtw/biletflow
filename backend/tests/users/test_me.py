import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.users.models import User
from tests.factories import auth_headers, create_organizer, create_user

URL = "/api/v1/me"


async def test_get_me_returns_the_signed_in_user(client: AsyncClient, db_session: AsyncSession):
    user = await create_user(db_session, full_name="Nurlan Abenov", phone="+77011234567")
    await db_session.commit()

    response = await client.get(URL, headers=auth_headers(user))

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == str(user.id)
    assert data["email"] == user.email
    assert data["full_name"] == "Nurlan Abenov"
    assert data["phone"] == "+77011234567"
    assert data["platform_role"] == "attendee"
    assert data["email_verified"] is False
    assert data["is_organizer"] is False
    assert "password_hash" not in data


async def test_get_me_reports_organizer_role(client: AsyncClient, db_session: AsyncSession):
    organizer = await create_organizer(db_session)
    user = await db_session.get_one(User, organizer.user_id)
    await db_session.commit()

    response = await client.get(URL, headers=auth_headers(user))

    assert response.json()["is_organizer"] is True


async def test_get_me_requires_authentication(client: AsyncClient):
    response = await client.get(URL)

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"


async def test_patch_me_updates_only_sent_fields(client: AsyncClient, db_session: AsyncSession):
    user = await create_user(db_session, full_name="Old Name", phone="+77010000000")
    await db_session.commit()

    response = await client.patch(
        URL, json={"full_name": "  Aliya Serik ", "locale": "en"}, headers=auth_headers(user)
    )

    assert response.status_code == 200
    data = response.json()
    assert data["full_name"] == "Aliya Serik"
    assert data["locale"] == "en"
    assert data["phone"] == "+77010000000"
    await db_session.refresh(user)
    assert (user.full_name, user.locale, user.phone) == ("Aliya Serik", "en", "+77010000000")


async def test_patch_me_null_phone_removes_it(client: AsyncClient, db_session: AsyncSession):
    user = await create_user(db_session, phone="+77010000000")
    await db_session.commit()

    response = await client.patch(URL, json={"phone": None}, headers=auth_headers(user))

    assert response.status_code == 200
    assert response.json()["phone"] is None


async def test_patch_me_ignores_email_and_role(client: AsyncClient, db_session: AsyncSession):
    user = await create_user(db_session)
    await db_session.commit()

    response = await client.patch(
        URL,
        json={"email": "new@example.com", "platform_role": "platform_admin"},
        headers=auth_headers(user),
    )

    assert response.status_code == 200
    await db_session.refresh(user)
    assert user.email != "new@example.com"
    assert user.platform_role == "attendee"


@pytest.mark.parametrize(
    "body",
    [{"full_name": None}, {"full_name": "   "}, {"locale": None}, {"locale": "de"}],
)
async def test_patch_me_invalid_input_returns_422_envelope(
    client: AsyncClient, db_session: AsyncSession, body
):
    user = await create_user(db_session)
    await db_session.commit()

    response = await client.patch(URL, json=body, headers=auth_headers(user))

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


async def test_patch_me_requires_authentication(client: AsyncClient):
    response = await client.patch(URL, json={"full_name": "X"})

    assert response.status_code == 401
