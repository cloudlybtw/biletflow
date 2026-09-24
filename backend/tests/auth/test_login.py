import asyncio
from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decode_access_token, hash_token
from app.modules.auth.models import UserToken, UserTokenPurpose
from app.modules.users.models import User, UserStatus
from tests.factories import DEFAULT_PASSWORD, create_user, create_user_token, unique_email

LOGIN_URL = "/api/v1/auth/login"
REFRESH_URL = "/api/v1/auth/refresh"
LOGOUT_URL = "/api/v1/auth/logout"
ME_URL = "/api/v1/me"


async def _login(client: AsyncClient, user: User, password: str = DEFAULT_PASSWORD):
    return await client.post(LOGIN_URL, json={"email": user.email, "password": password})


async def _refresh_tokens(session: AsyncSession, user: User) -> list[UserToken]:
    result = await session.scalars(
        select(UserToken)
        .where(UserToken.user_id == user.id, UserToken.purpose == UserTokenPurpose.REFRESH)
        .order_by(UserToken.created_at)
        .execution_options(populate_existing=True)
    )
    return list(result.all())


# --- login ------------------------------------------------------------------


async def test_login_returns_access_and_refresh_tokens(
    client: AsyncClient, db_session: AsyncSession
):
    user = await create_user(db_session)
    await db_session.commit()

    response = await _login(client, user)

    assert response.status_code == 200
    data = response.json()
    assert data["token_type"] == "bearer"
    assert data["expires_in"] == 15 * 60
    assert data["user"]["id"] == str(user.id)
    assert decode_access_token(data["access_token"]) == user.id
    (stored,) = await _refresh_tokens(db_session, user)
    assert stored.token_hash == hash_token(data["refresh_token"])
    assert stored.used_at is None
    assert abs(stored.expires_at - (datetime.now(UTC) + timedelta(days=30))) < timedelta(minutes=1)


async def test_login_records_last_login_at(client: AsyncClient, db_session: AsyncSession):
    user = await create_user(db_session)
    await db_session.commit()

    await _login(client, user)

    await db_session.refresh(user)
    assert user.last_login_at is not None


async def test_access_token_from_login_authenticates_requests(
    client: AsyncClient, db_session: AsyncSession
):
    user = await create_user(db_session)
    await db_session.commit()
    token = (await _login(client, user)).json()["access_token"]

    response = await client.get(ME_URL, headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    assert response.json()["id"] == str(user.id)


async def test_unverified_user_can_log_in(client: AsyncClient, db_session: AsyncSession):
    user = await create_user(db_session, email_verified_at=None)
    await db_session.commit()

    response = await _login(client, user)

    assert response.status_code == 200
    assert response.json()["user"]["email_verified"] is False


async def test_login_matches_email_case_insensitively(
    client: AsyncClient, db_session: AsyncSession
):
    await create_user(db_session, email="Madina@Example.com")
    await db_session.commit()

    response = await client.post(
        LOGIN_URL, json={"email": "madina@example.com", "password": DEFAULT_PASSWORD}
    )

    assert response.status_code == 200


async def test_login_rejects_wrong_password(client: AsyncClient, db_session: AsyncSession):
    user = await create_user(db_session)
    await db_session.commit()

    response = await _login(client, user, password="wrong-password")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INVALID_CREDENTIALS"
    assert await _refresh_tokens(db_session, user) == []


async def test_login_rejects_unknown_email_like_wrong_password(client: AsyncClient):
    response = await client.post(
        LOGIN_URL, json={"email": unique_email(), "password": DEFAULT_PASSWORD}
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INVALID_CREDENTIALS"


async def test_suspended_user_cannot_log_in(client: AsyncClient, db_session: AsyncSession):
    user = await create_user(db_session, status=UserStatus.SUSPENDED)
    await db_session.commit()

    response = await _login(client, user)

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "ACCOUNT_SUSPENDED"
    assert await _refresh_tokens(db_session, user) == []


async def test_suspended_user_with_wrong_password_gets_invalid_credentials(
    client: AsyncClient, db_session: AsyncSession
):
    user = await create_user(db_session, status=UserStatus.SUSPENDED)
    await db_session.commit()

    response = await _login(client, user, password="wrong-password")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INVALID_CREDENTIALS"


async def test_deleted_user_cannot_log_in(client: AsyncClient, db_session: AsyncSession):
    user = await create_user(db_session, status=UserStatus.DELETED)
    await db_session.commit()

    response = await _login(client, user)

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INVALID_CREDENTIALS"


@pytest.mark.parametrize("body", [{}, {"email": "nope", "password": "x"}, {"email": "a@b.co"}])
async def test_login_invalid_input_returns_422_envelope(client: AsyncClient, body):
    response = await client.post(LOGIN_URL, json=body)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


# --- refresh ----------------------------------------------------------------


async def test_refresh_rotates_the_refresh_token(client: AsyncClient, db_session: AsyncSession):
    user = await create_user(db_session)
    await db_session.commit()
    first = (await _login(client, user)).json()

    response = await client.post(REFRESH_URL, json={"refresh_token": first["refresh_token"]})

    assert response.status_code == 200
    second = response.json()
    assert second["refresh_token"] != first["refresh_token"]
    assert decode_access_token(second["access_token"]) == user.id
    old, new = await _refresh_tokens(db_session, user)
    assert old.used_at is not None
    assert new.used_at is None
    assert new.token_hash == hash_token(second["refresh_token"])


async def test_refresh_token_is_single_use(client: AsyncClient, db_session: AsyncSession):
    user = await create_user(db_session)
    await db_session.commit()
    refresh_token = (await _login(client, user)).json()["refresh_token"]
    await client.post(REFRESH_URL, json={"refresh_token": refresh_token})

    response = await client.post(REFRESH_URL, json={"refresh_token": refresh_token})

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "REFRESH_TOKEN_INVALID"


async def test_refresh_rejects_expired_token(client: AsyncClient, db_session: AsyncSession):
    user = await create_user(db_session)
    raw, _ = await create_user_token(
        db_session,
        user,
        purpose=UserTokenPurpose.REFRESH,
        expires_at=datetime.now(UTC) - timedelta(seconds=1),
    )
    await db_session.commit()

    response = await client.post(REFRESH_URL, json={"refresh_token": raw})

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "REFRESH_TOKEN_INVALID"


async def test_refresh_rejects_unknown_token(client: AsyncClient):
    response = await client.post(REFRESH_URL, json={"refresh_token": "not-a-real-token"})

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "REFRESH_TOKEN_INVALID"


async def test_refresh_rejects_token_of_another_purpose(
    client: AsyncClient, db_session: AsyncSession
):
    user = await create_user(db_session)
    raw, _ = await create_user_token(db_session, user, purpose=UserTokenPurpose.PASSWORD_RESET)
    await db_session.commit()

    response = await client.post(REFRESH_URL, json={"refresh_token": raw})

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "REFRESH_TOKEN_INVALID"


async def test_refresh_rejects_an_access_token(client: AsyncClient, db_session: AsyncSession):
    user = await create_user(db_session)
    await db_session.commit()
    access_token = (await _login(client, user)).json()["access_token"]

    response = await client.post(REFRESH_URL, json={"refresh_token": access_token})

    assert response.status_code == 401


async def test_concurrent_refreshes_of_same_token_have_one_winner(
    client: AsyncClient, db_session: AsyncSession
):
    user = await create_user(db_session)
    await db_session.commit()
    refresh_token = (await _login(client, user)).json()["refresh_token"]

    responses = await asyncio.gather(
        *(client.post(REFRESH_URL, json={"refresh_token": refresh_token}) for _ in range(5))
    )

    assert sorted(r.status_code for r in responses) == [200, 401, 401, 401, 401]
    active = [t for t in await _refresh_tokens(db_session, user) if t.used_at is None]
    assert len(active) == 1


async def test_suspended_user_cannot_refresh(client: AsyncClient, db_session: AsyncSession):
    user = await create_user(db_session)
    await db_session.commit()
    refresh_token = (await _login(client, user)).json()["refresh_token"]
    user.status = UserStatus.SUSPENDED
    await db_session.commit()

    response = await client.post(REFRESH_URL, json={"refresh_token": refresh_token})

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "ACCOUNT_SUSPENDED"
    assert all(t.used_at is not None for t in await _refresh_tokens(db_session, user))


async def test_deleted_user_cannot_refresh(client: AsyncClient, db_session: AsyncSession):
    user = await create_user(db_session)
    await db_session.commit()
    refresh_token = (await _login(client, user)).json()["refresh_token"]
    user.status = UserStatus.DELETED
    await db_session.commit()

    response = await client.post(REFRESH_URL, json={"refresh_token": refresh_token})

    assert response.status_code == 401


# --- logout -----------------------------------------------------------------


async def test_logout_revokes_the_refresh_token(client: AsyncClient, db_session: AsyncSession):
    user = await create_user(db_session)
    await db_session.commit()
    refresh_token = (await _login(client, user)).json()["refresh_token"]

    response = await client.post(LOGOUT_URL, json={"refresh_token": refresh_token})

    assert response.status_code == 204
    assert response.content == b""
    refresh = await client.post(REFRESH_URL, json={"refresh_token": refresh_token})
    assert refresh.status_code == 401


async def test_logout_leaves_other_sessions_signed_in(
    client: AsyncClient, db_session: AsyncSession
):
    user = await create_user(db_session)
    await db_session.commit()
    phone = (await _login(client, user)).json()["refresh_token"]
    laptop = (await _login(client, user)).json()["refresh_token"]

    await client.post(LOGOUT_URL, json={"refresh_token": phone})

    response = await client.post(REFRESH_URL, json={"refresh_token": laptop})
    assert response.status_code == 200


async def test_logout_with_unknown_token_returns_204(client: AsyncClient):
    response = await client.post(LOGOUT_URL, json={"refresh_token": "not-a-real-token"})

    assert response.status_code == 204


async def test_logout_without_token_returns_422_envelope(client: AsyncClient):
    response = await client.post(LOGOUT_URL, json={})

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
