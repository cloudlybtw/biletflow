import asyncio
from datetime import UTC, datetime, timedelta
from urllib.parse import parse_qs, urlparse

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_token, verify_password
from app.modules.auth.models import UserToken, UserTokenPurpose
from app.modules.notifications.models import Notification, NotificationChannel, NotificationType
from app.modules.users.models import User, UserStatus
from tests.factories import DEFAULT_PASSWORD, create_user, create_user_token, unique_email

FORGOT_URL = "/api/v1/auth/password/forgot"
RESET_URL = "/api/v1/auth/password/reset"
LOGIN_URL = "/api/v1/auth/login"
REFRESH_URL = "/api/v1/auth/refresh"
NEW_PASSWORD = "brand-new-pass-42"


def _raw_token(notification: Notification) -> str:
    return parse_qs(urlparse(notification.payload["reset_url"]).query)["token"][0]


async def _reset_tokens(session: AsyncSession, user: User) -> list[UserToken]:
    result = await session.scalars(
        select(UserToken)
        .where(UserToken.user_id == user.id, UserToken.purpose == UserTokenPurpose.PASSWORD_RESET)
        .order_by(UserToken.created_at)
        .execution_options(populate_existing=True)
    )
    return list(result.all())


async def _notifications(session: AsyncSession, user: User) -> list[Notification]:
    result = await session.scalars(select(Notification).where(Notification.user_id == user.id))
    return list(result.all())


async def _reset_token_for(session: AsyncSession, user: User, **overrides) -> str:
    raw, _ = await create_user_token(
        session, user, purpose=UserTokenPurpose.PASSWORD_RESET, **overrides
    )
    await session.commit()
    return raw


# --- forgot -----------------------------------------------------------------


async def test_forgot_password_queues_reset_email_with_hashed_token(
    client: AsyncClient, db_session: AsyncSession
):
    user = await create_user(db_session)
    await db_session.commit()

    response = await client.post(FORGOT_URL, json={"email": user.email})

    assert response.status_code == 202
    assert response.content == b""
    (token,) = await _reset_tokens(db_session, user)
    assert token.used_at is None
    expected_expiry = datetime.now(UTC) + timedelta(minutes=60)
    assert abs(token.expires_at - expected_expiry) < timedelta(minutes=1)
    (notification,) = await _notifications(db_session, user)
    assert notification.type is NotificationType.PASSWORD_RESET
    assert notification.channel is NotificationChannel.EMAIL
    assert notification.payload["reset_url"].startswith("http://localhost:5173/reset-password?")
    assert hash_token(_raw_token(notification)) == token.token_hash


async def test_forgot_password_invalidates_older_links(
    client: AsyncClient, db_session: AsyncSession
):
    user = await create_user(db_session)
    old_raw = await _reset_token_for(
        db_session, user, created_at=datetime.now(UTC) - timedelta(minutes=5)
    )

    await client.post(FORGOT_URL, json={"email": user.email})

    old, new = await _reset_tokens(db_session, user)
    assert old.used_at is not None
    assert new.used_at is None
    response = await client.post(RESET_URL, json={"token": old_raw, "new_password": NEW_PASSWORD})
    assert response.json()["error"]["code"] == "RESET_TOKEN_INVALID"


async def test_forgot_password_within_cooldown_sends_nothing(
    client: AsyncClient, db_session: AsyncSession
):
    user = await create_user(db_session)
    await _reset_token_for(db_session, user)

    response = await client.post(FORGOT_URL, json={"email": user.email})

    assert response.status_code == 202
    assert len(await _reset_tokens(db_session, user)) == 1
    assert await _notifications(db_session, user) == []


async def test_forgot_password_for_unknown_email_returns_202(
    client: AsyncClient, db_session: AsyncSession
):
    response = await client.post(FORGOT_URL, json={"email": unique_email()})

    assert response.status_code == 202
    assert (await db_session.scalars(select(UserToken))).all() == []
    assert (await db_session.scalars(select(Notification))).all() == []


async def test_forgot_password_for_suspended_user_sends_nothing(
    client: AsyncClient, db_session: AsyncSession
):
    user = await create_user(db_session, status=UserStatus.SUSPENDED)
    await db_session.commit()

    response = await client.post(FORGOT_URL, json={"email": user.email})

    assert response.status_code == 202
    assert await _reset_tokens(db_session, user) == []
    assert await _notifications(db_session, user) == []


async def test_forgot_password_with_invalid_email_returns_422_envelope(client: AsyncClient):
    response = await client.post(FORGOT_URL, json={"email": "nope"})

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


# --- reset ------------------------------------------------------------------


async def test_reset_password_sets_new_password(client: AsyncClient, db_session: AsyncSession):
    user = await create_user(db_session)
    await db_session.commit()
    await client.post(FORGOT_URL, json={"email": user.email})
    (notification,) = await _notifications(db_session, user)

    response = await client.post(
        RESET_URL, json={"token": _raw_token(notification), "new_password": NEW_PASSWORD}
    )

    assert response.status_code == 204
    await db_session.refresh(user)
    assert verify_password(user.password_hash, NEW_PASSWORD)
    new_login = await client.post(LOGIN_URL, json={"email": user.email, "password": NEW_PASSWORD})
    assert new_login.status_code == 200
    old_login = await client.post(
        LOGIN_URL, json={"email": user.email, "password": DEFAULT_PASSWORD}
    )
    assert old_login.status_code == 401


async def test_reset_password_revokes_all_refresh_tokens(
    client: AsyncClient, db_session: AsyncSession
):
    user = await create_user(db_session)
    await db_session.commit()
    login_body = {"email": user.email, "password": DEFAULT_PASSWORD}
    sessions = [(await client.post(LOGIN_URL, json=login_body)).json() for _ in range(2)]
    raw = await _reset_token_for(db_session, user)

    await client.post(RESET_URL, json={"token": raw, "new_password": NEW_PASSWORD})

    for s in sessions:
        response = await client.post(REFRESH_URL, json={"refresh_token": s["refresh_token"]})
        assert response.status_code == 401


async def test_reset_password_marks_email_verified(client: AsyncClient, db_session: AsyncSession):
    user = await create_user(db_session, email_verified_at=None)
    raw = await _reset_token_for(db_session, user)

    await client.post(RESET_URL, json={"token": raw, "new_password": NEW_PASSWORD})

    await db_session.refresh(user)
    assert user.email_verified_at is not None


async def test_reset_token_is_single_use(client: AsyncClient, db_session: AsyncSession):
    user = await create_user(db_session)
    raw = await _reset_token_for(db_session, user)
    await client.post(RESET_URL, json={"token": raw, "new_password": NEW_PASSWORD})

    response = await client.post(RESET_URL, json={"token": raw, "new_password": "another-pass-1"})

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "RESET_TOKEN_INVALID"
    await db_session.refresh(user)
    assert verify_password(user.password_hash, NEW_PASSWORD)


async def test_reset_password_rejects_expired_token(client: AsyncClient, db_session: AsyncSession):
    user = await create_user(db_session)
    raw = await _reset_token_for(
        db_session, user, expires_at=datetime.now(UTC) - timedelta(minutes=1)
    )

    response = await client.post(RESET_URL, json={"token": raw, "new_password": NEW_PASSWORD})

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "RESET_TOKEN_EXPIRED"
    await db_session.refresh(user)
    assert verify_password(user.password_hash, DEFAULT_PASSWORD)


async def test_reset_password_rejects_unknown_token(client: AsyncClient):
    response = await client.post(
        RESET_URL, json={"token": "not-a-real-token", "new_password": NEW_PASSWORD}
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "RESET_TOKEN_INVALID"


async def test_reset_password_rejects_verification_token(
    client: AsyncClient, db_session: AsyncSession
):
    user = await create_user(db_session)
    raw, _ = await create_user_token(db_session, user, purpose=UserTokenPurpose.EMAIL_VERIFY)
    await db_session.commit()

    response = await client.post(RESET_URL, json={"token": raw, "new_password": NEW_PASSWORD})

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "RESET_TOKEN_INVALID"


async def test_reset_password_enforces_password_policy(
    client: AsyncClient, db_session: AsyncSession
):
    user = await create_user(db_session)
    raw = await _reset_token_for(db_session, user)

    response = await client.post(RESET_URL, json={"token": raw, "new_password": "short"})

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
    (token,) = await _reset_tokens(db_session, user)
    assert token.used_at is None


async def test_concurrent_resets_with_same_token_have_one_winner(
    client: AsyncClient, db_session: AsyncSession
):
    user = await create_user(db_session)
    raw = await _reset_token_for(db_session, user)
    passwords = [f"racing-password-{i}" for i in range(5)]

    responses = await asyncio.gather(
        *(client.post(RESET_URL, json={"token": raw, "new_password": p}) for p in passwords)
    )

    codes = [r.status_code for r in responses]
    assert sorted(codes) == [204, 400, 400, 400, 400]
    winner = passwords[codes.index(204)]
    await db_session.refresh(user)
    assert verify_password(user.password_hash, winner)
