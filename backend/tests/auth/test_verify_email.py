import asyncio
from datetime import UTC, datetime, timedelta
from urllib.parse import parse_qs, urlparse

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.models import UserToken, UserTokenPurpose
from app.modules.notifications.models import Notification, NotificationType
from app.modules.users.models import User, UserStatus
from tests.factories import create_user, create_user_token, unique_email

VERIFY_URL = "/api/v1/auth/verify-email"
RESEND_URL = "/api/v1/auth/verify-email/resend"


def _raw_token(notification: Notification) -> str:
    return parse_qs(urlparse(notification.payload["verify_url"]).query)["token"][0]


async def _tokens(session: AsyncSession, user: User) -> list[UserToken]:
    result = await session.scalars(
        select(UserToken)
        .where(UserToken.user_id == user.id)
        .order_by(UserToken.created_at)
        .execution_options(populate_existing=True)
    )
    return list(result.all())


async def _notifications(session: AsyncSession, user: User) -> list[Notification]:
    result = await session.scalars(select(Notification).where(Notification.user_id == user.id))
    return list(result.all())


async def _unverified_user_with_old_token(session: AsyncSession) -> tuple[User, str]:
    """A user whose last link is older than the resend cooldown."""
    user = await create_user(session)
    raw, _ = await create_user_token(
        session, user, created_at=datetime.now(UTC) - timedelta(minutes=5)
    )
    await session.commit()
    return user, raw


# --- verify -----------------------------------------------------------------


async def test_verify_email_marks_user_verified_and_uses_token(
    client: AsyncClient, db_session: AsyncSession
):
    user = await create_user(db_session)
    raw, token = await create_user_token(db_session, user)
    await db_session.commit()

    response = await client.post(VERIFY_URL, json={"token": raw})

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == str(user.id)
    assert data["email_verified"] is True
    await db_session.refresh(user)
    await db_session.refresh(token)
    assert user.email_verified_at is not None
    assert token.used_at is not None


async def test_register_then_verify_with_link_from_email(
    client: AsyncClient, db_session: AsyncSession
):
    email = unique_email()
    register = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "s3cret-pass", "full_name": "Arman Nurlanov"},
    )
    notification = await db_session.scalar(
        select(Notification).where(Notification.user_id == register.json()["id"])
    )

    response = await client.post(VERIFY_URL, json={"token": _raw_token(notification)})

    assert response.status_code == 200
    assert response.json()["email_verified"] is True


async def test_verify_email_rejects_expired_token(client: AsyncClient, db_session: AsyncSession):
    user = await create_user(db_session)
    raw, _ = await create_user_token(
        db_session, user, expires_at=datetime.now(UTC) - timedelta(minutes=1)
    )
    await db_session.commit()

    response = await client.post(VERIFY_URL, json={"token": raw})

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VERIFICATION_TOKEN_EXPIRED"
    await db_session.refresh(user)
    assert user.email_verified_at is None


async def test_verify_email_rejects_unknown_token(client: AsyncClient):
    response = await client.post(VERIFY_URL, json={"token": "not-a-real-token"})

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VERIFICATION_TOKEN_INVALID"


async def test_verify_email_rejects_token_of_another_purpose(
    client: AsyncClient, db_session: AsyncSession
):
    user = await create_user(db_session)
    raw, _ = await create_user_token(db_session, user, purpose=UserTokenPurpose.PASSWORD_RESET)
    await db_session.commit()

    response = await client.post(VERIFY_URL, json={"token": raw})

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VERIFICATION_TOKEN_INVALID"
    await db_session.refresh(user)
    assert user.email_verified_at is None


async def test_verify_email_is_idempotent_for_a_redeemed_token(
    client: AsyncClient, db_session: AsyncSession
):
    user = await create_user(db_session)
    raw, _ = await create_user_token(db_session, user)
    await db_session.commit()
    await client.post(VERIFY_URL, json={"token": raw})
    await db_session.refresh(user)
    verified_at = user.email_verified_at

    response = await client.post(VERIFY_URL, json={"token": raw})

    assert response.status_code == 200
    assert response.json()["email_verified"] is True
    await db_session.refresh(user)
    assert user.email_verified_at == verified_at


async def test_verify_email_rejects_link_superseded_by_resend(
    client: AsyncClient, db_session: AsyncSession
):
    user, old_raw = await _unverified_user_with_old_token(db_session)
    await client.post(RESEND_URL, json={"email": user.email})

    response = await client.post(VERIFY_URL, json={"token": old_raw})

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VERIFICATION_TOKEN_INVALID"


async def test_verify_email_invalidates_other_pending_links(
    client: AsyncClient, db_session: AsyncSession
):
    user = await create_user(db_session)
    raw, _ = await create_user_token(db_session, user)
    await create_user_token(db_session, user)
    await db_session.commit()

    await client.post(VERIFY_URL, json={"token": raw})

    assert all(t.used_at is not None for t in await _tokens(db_session, user))


async def test_concurrent_verifications_of_same_token_claim_it_once(
    client: AsyncClient, db_session: AsyncSession
):
    user = await create_user(db_session)
    raw, token = await create_user_token(db_session, user)
    await db_session.commit()

    responses = await asyncio.gather(
        *(client.post(VERIFY_URL, json={"token": raw}) for _ in range(5))
    )

    assert [r.status_code for r in responses] == [200] * 5
    await db_session.refresh(user)
    await db_session.refresh(token)
    # Both columns are now() of the single transaction that won the claim.
    assert user.email_verified_at == token.used_at


async def test_verify_email_without_token_returns_422_envelope(client: AsyncClient):
    response = await client.post(VERIFY_URL, json={})

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


# --- resend -----------------------------------------------------------------


async def test_resend_issues_new_link_and_invalidates_old_one(
    client: AsyncClient, db_session: AsyncSession
):
    user, _ = await _unverified_user_with_old_token(db_session)

    response = await client.post(RESEND_URL, json={"email": user.email})

    assert response.status_code == 202
    assert response.content == b""
    old, new = await _tokens(db_session, user)
    assert old.used_at is not None
    assert new.used_at is None
    assert new.purpose is UserTokenPurpose.EMAIL_VERIFY
    (notification,) = await _notifications(db_session, user)
    assert notification.type is NotificationType.ACCOUNT_VERIFICATION

    verify = await client.post(VERIFY_URL, json={"token": _raw_token(notification)})
    assert verify.status_code == 200


async def test_resend_matches_email_case_insensitively(
    client: AsyncClient, db_session: AsyncSession
):
    user = await create_user(db_session, email="Aruzhan@Example.com")
    await create_user_token(db_session, user, created_at=datetime.now(UTC) - timedelta(minutes=5))
    await db_session.commit()

    response = await client.post(RESEND_URL, json={"email": "aruzhan@example.com"})

    assert response.status_code == 202
    assert len(await _tokens(db_session, user)) == 2


async def test_resend_within_cooldown_sends_nothing(client: AsyncClient, db_session: AsyncSession):
    user = await create_user(db_session)
    await create_user_token(db_session, user)
    await db_session.commit()

    response = await client.post(RESEND_URL, json={"email": user.email})

    assert response.status_code == 202
    assert len(await _tokens(db_session, user)) == 1
    assert await _notifications(db_session, user) == []


async def test_resend_for_unknown_email_returns_202(client: AsyncClient, db_session: AsyncSession):
    response = await client.post(RESEND_URL, json={"email": unique_email()})

    assert response.status_code == 202
    assert (await db_session.scalars(select(UserToken))).all() == []
    assert (await db_session.scalars(select(Notification))).all() == []


async def test_resend_for_verified_user_sends_nothing(
    client: AsyncClient, db_session: AsyncSession
):
    user = await create_user(db_session, email_verified_at=datetime.now(UTC))
    await db_session.commit()

    response = await client.post(RESEND_URL, json={"email": user.email})

    assert response.status_code == 202
    assert await _tokens(db_session, user) == []
    assert await _notifications(db_session, user) == []


async def test_resend_for_suspended_user_sends_nothing(
    client: AsyncClient, db_session: AsyncSession
):
    user = await create_user(db_session, status=UserStatus.SUSPENDED)
    await db_session.commit()

    response = await client.post(RESEND_URL, json={"email": user.email})

    assert response.status_code == 202
    assert await _tokens(db_session, user) == []
    assert await _notifications(db_session, user) == []


async def test_resend_with_invalid_email_returns_422_envelope(client: AsyncClient):
    response = await client.post(RESEND_URL, json={"email": "nope"})

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
