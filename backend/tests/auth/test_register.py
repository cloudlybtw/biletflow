import asyncio
from datetime import UTC, datetime, timedelta
from urllib.parse import parse_qs, urlparse

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_token, verify_password
from app.modules.auth.models import UserToken, UserTokenPurpose
from app.modules.notifications.models import (
    Notification,
    NotificationChannel,
    NotificationStatus,
    NotificationType,
)
from app.modules.users.models import User
from tests.factories import create_user, unique_email

URL = "/api/v1/auth/register"


def _payload(**overrides) -> dict:
    body = {
        "email": unique_email(),
        "password": "s3cret-pass",
        "full_name": "Aigerim Sadykova",
        "locale": "kk",
    }
    body.update(overrides)
    return body


async def test_register_creates_unverified_attendee(client: AsyncClient, db_session: AsyncSession):
    body = _payload(full_name="  Aigerim Sadykova  ")

    response = await client.post(URL, json=body)

    assert response.status_code == 201
    data = response.json()
    assert data["email"] == body["email"]
    assert data["full_name"] == "Aigerim Sadykova"
    assert data["locale"] == "kk"
    assert data["platform_role"] == "attendee"
    assert data["email_verified"] is False
    assert "password" not in data and "password_hash" not in data

    user = await db_session.scalar(select(User).where(User.email == body["email"]))
    assert user.password_hash.startswith("$argon2id$")
    assert verify_password(user.password_hash, body["password"])


async def test_register_stores_hashed_verification_token_and_queues_email(
    client: AsyncClient, db_session: AsyncSession
):
    response = await client.post(URL, json=_payload())
    user_id = response.json()["id"]

    token = await db_session.scalar(select(UserToken).where(UserToken.user_id == user_id))
    assert token.purpose is UserTokenPurpose.EMAIL_VERIFY
    assert token.used_at is None
    expected_expiry = datetime.now(UTC) + timedelta(hours=24)
    assert abs(token.expires_at - expected_expiry) < timedelta(minutes=1)

    notification = await db_session.scalar(
        select(Notification).where(Notification.user_id == user_id)
    )
    assert notification.type is NotificationType.ACCOUNT_VERIFICATION
    assert notification.channel is NotificationChannel.EMAIL
    assert notification.status is NotificationStatus.QUEUED
    assert notification.related_entity_id == user_id

    raw_token = parse_qs(urlparse(notification.payload["verify_url"]).query)["token"][0]
    assert raw_token != token.token_hash
    assert hash_token(raw_token) == token.token_hash


async def test_register_rejects_duplicate_email_case_insensitively(
    client: AsyncClient, db_session: AsyncSession
):
    existing = await create_user(db_session, email="Dana@Example.com")
    await db_session.commit()

    response = await client.post(URL, json=_payload(email="dana@example.com"))

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "EMAIL_TAKEN"
    users = (await db_session.scalars(select(User))).all()
    assert [u.id for u in users] == [existing.id]


async def test_concurrent_registrations_with_same_email_have_one_winner(
    client: AsyncClient, db_session: AsyncSession
):
    body = _payload()

    responses = await asyncio.gather(*(client.post(URL, json=body) for _ in range(5)))

    codes = sorted(r.status_code for r in responses)
    assert codes == [201, 409, 409, 409, 409]
    assert len((await db_session.scalars(select(User))).all()) == 1
    assert len((await db_session.scalars(select(UserToken))).all()) == 1
    assert len((await db_session.scalars(select(Notification))).all()) == 1


async def test_register_defaults_locale_to_ru(client: AsyncClient):
    body = _payload()
    del body["locale"]

    response = await client.post(URL, json=body)

    assert response.status_code == 201
    assert response.json()["locale"] == "ru"


@pytest.mark.parametrize(
    "overrides",
    [
        {"email": "not-an-email"},
        {"password": "short"},
        {"full_name": "   "},
        {"locale": "de"},
    ],
)
async def test_register_invalid_input_returns_422_envelope(client: AsyncClient, overrides):
    response = await client.post(URL, json=_payload(**overrides))

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
