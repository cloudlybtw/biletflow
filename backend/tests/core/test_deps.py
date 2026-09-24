"""Tests for every auth/permission dependency, via throwaway routes on the test app."""

import uuid
from datetime import UTC, datetime, timedelta

import jwt
import pytest
from fastapi import Depends, FastAPI
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.deps import (
    EventAccess,
    current_user,
    require_event_role,
    require_platform_admin,
    require_verified,
)
from app.modules.users.models import PlatformRole, StaffRole, User, UserStatus
from tests.factories import (
    auth_headers,
    create_event,
    create_organizer,
    create_staff_assignment,
    create_user,
    create_verified_user,
)

# Build role dependencies once at import, as real routers should.
owner_only = require_event_role()
checkin_staff = require_event_role(StaffRole.EVENT_ADMIN, StaffRole.CO_ORGANIZER)
moderation = require_event_role(StaffRole.CO_ORGANIZER, allow_platform_admin=True)


@pytest.fixture(autouse=True)
def _probe_routes(app: FastAPI) -> None:
    @app.get("/probe/user")
    async def probe_user(user: User = Depends(current_user)) -> dict:
        return {"user_id": str(user.id)}

    @app.get("/probe/verified")
    async def probe_verified(user: User = Depends(require_verified)) -> dict:
        return {"user_id": str(user.id)}

    @app.get("/probe/admin")
    async def probe_admin(user: User = Depends(require_platform_admin)) -> dict:
        return {"user_id": str(user.id)}

    def _access(access: EventAccess) -> dict:
        return {
            "is_owner": access.is_owner,
            "staff_roles": sorted(access.staff_roles),
            "actor_role": access.actor_role,
        }

    @app.get("/probe/events/{event_id}/owner")
    async def probe_owner(access: EventAccess = Depends(owner_only)) -> dict:
        return _access(access)

    @app.get("/probe/events/{event_id}/checkin")
    async def probe_checkin(
        access: EventAccess = Depends(checkin_staff),
    ) -> dict:
        return _access(access)

    @app.get("/probe/events/{event_id}/moderation")
    async def probe_moderation(
        access: EventAccess = Depends(moderation),
    ) -> dict:
        return _access(access)


def _token(**claims) -> str:
    settings = get_settings()
    now = datetime.now(UTC)
    body = {"typ": "access", "iat": now, "exp": now + timedelta(minutes=5)} | claims
    return jwt.encode(body, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


# --- current_user -----------------------------------------------------------


async def test_current_user_accepts_valid_token(client: AsyncClient, db_session: AsyncSession):
    user = await create_user(db_session)
    await db_session.commit()

    response = await client.get("/probe/user", headers=auth_headers(user))

    assert response.status_code == 200
    assert response.json() == {"user_id": str(user.id)}


async def test_current_user_requires_a_token(client: AsyncClient):
    response = await client.get("/probe/user")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"


@pytest.mark.parametrize(
    "headers",
    [
        {"Authorization": "Bearer not-a-jwt"},
        {"Authorization": "Basic dXNlcjpwYXNz"},
    ],
)
async def test_current_user_rejects_malformed_credentials(client: AsyncClient, headers):
    response = await client.get("/probe/user", headers=headers)

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"


async def test_current_user_reports_expired_token(client: AsyncClient, db_session: AsyncSession):
    user = await create_user(db_session)
    await db_session.commit()
    expired = _token(sub=str(user.id), exp=datetime.now(UTC) - timedelta(seconds=1))

    response = await client.get("/probe/user", headers=_bearer(expired))

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "TOKEN_EXPIRED"


async def test_current_user_rejects_token_signed_with_another_key(
    client: AsyncClient, db_session: AsyncSession
):
    user = await create_user(db_session)
    await db_session.commit()
    forged = jwt.encode(
        {"sub": str(user.id), "typ": "access", "exp": datetime.now(UTC) + timedelta(minutes=5)},
        "an-attacker-chosen-secret-of-32-bytes!",
        algorithm="HS256",
    )

    response = await client.get("/probe/user", headers=_bearer(forged))

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"


async def test_current_user_rejects_non_access_token_type(
    client: AsyncClient, db_session: AsyncSession
):
    user = await create_user(db_session)
    await db_session.commit()

    response = await client.get("/probe/user", headers=_bearer(_token(sub=str(user.id), typ="x")))

    assert response.status_code == 401


async def test_current_user_rejects_token_for_unknown_user(client: AsyncClient):
    response = await client.get("/probe/user", headers=_bearer(_token(sub=str(uuid.uuid4()))))

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"


async def test_current_user_rejects_suspended_user_with_live_token(
    client: AsyncClient, db_session: AsyncSession
):
    user = await create_user(db_session)
    await db_session.commit()
    headers = auth_headers(user)
    user.status = UserStatus.SUSPENDED
    await db_session.commit()

    response = await client.get("/probe/user", headers=headers)

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "ACCOUNT_SUSPENDED"


async def test_current_user_rejects_deleted_user(client: AsyncClient, db_session: AsyncSession):
    user = await create_user(db_session, status=UserStatus.DELETED)
    await db_session.commit()

    response = await client.get("/probe/user", headers=auth_headers(user))

    assert response.status_code == 401


# --- require_verified / require_platform_admin -------------------------------


async def test_require_verified_rejects_unverified_user(
    client: AsyncClient, db_session: AsyncSession
):
    user = await create_user(db_session)
    await db_session.commit()

    response = await client.get("/probe/verified", headers=auth_headers(user))

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "EMAIL_NOT_VERIFIED"


async def test_require_verified_accepts_verified_user(
    client: AsyncClient, db_session: AsyncSession
):
    user = await create_verified_user(db_session)
    await db_session.commit()

    response = await client.get("/probe/verified", headers=auth_headers(user))

    assert response.status_code == 200


async def test_require_platform_admin_rejects_attendee(
    client: AsyncClient, db_session: AsyncSession
):
    user = await create_verified_user(db_session)
    await db_session.commit()

    response = await client.get("/probe/admin", headers=auth_headers(user))

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"


async def test_require_platform_admin_accepts_admin(client: AsyncClient, db_session: AsyncSession):
    admin = await create_verified_user(db_session, platform_role=PlatformRole.PLATFORM_ADMIN)
    await db_session.commit()

    response = await client.get("/probe/admin", headers=auth_headers(admin))

    assert response.status_code == 200


async def test_require_platform_admin_requires_authentication(client: AsyncClient):
    response = await client.get("/probe/admin")

    assert response.status_code == 401


# --- require_event_role -----------------------------------------------------


async def _event_with_owner(session: AsyncSession) -> tuple[uuid.UUID, User]:
    owner = await create_verified_user(session)
    organizer = await create_organizer(session, user=owner)
    event_id = await create_event(session, organizer)
    return event_id, owner


async def test_event_owner_passes_every_event_check(client: AsyncClient, db_session: AsyncSession):
    event_id, owner = await _event_with_owner(db_session)
    await db_session.commit()

    for path in ("owner", "checkin", "moderation"):
        response = await client.get(f"/probe/events/{event_id}/{path}", headers=auth_headers(owner))
        assert response.status_code == 200, path
        assert response.json() == {"is_owner": True, "staff_roles": [], "actor_role": "organizer"}


async def test_staff_with_required_role_passes(client: AsyncClient, db_session: AsyncSession):
    event_id, _ = await _event_with_owner(db_session)
    scanner = await create_verified_user(db_session)
    await create_staff_assignment(db_session, event_id, scanner, StaffRole.EVENT_ADMIN)
    await db_session.commit()

    response = await client.get(f"/probe/events/{event_id}/checkin", headers=auth_headers(scanner))

    assert response.status_code == 200
    assert response.json() == {
        "is_owner": False,
        "staff_roles": ["event_admin"],
        "actor_role": "event_admin",
    }


async def test_staff_with_other_role_gets_403(client: AsyncClient, db_session: AsyncSession):
    event_id, _ = await _event_with_owner(db_session)
    agent = await create_verified_user(db_session)
    await create_staff_assignment(db_session, event_id, agent, StaffRole.SUPPORT_AGENT)
    await db_session.commit()

    response = await client.get(f"/probe/events/{event_id}/checkin", headers=auth_headers(agent))

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"


async def test_owner_only_check_rejects_co_organizer(client: AsyncClient, db_session: AsyncSession):
    event_id, _ = await _event_with_owner(db_session)
    co = await create_verified_user(db_session)
    await create_staff_assignment(db_session, event_id, co, StaffRole.CO_ORGANIZER)
    await db_session.commit()

    response = await client.get(f"/probe/events/{event_id}/owner", headers=auth_headers(co))

    assert response.status_code == 403


async def test_revoked_staff_assignment_grants_nothing(
    client: AsyncClient, db_session: AsyncSession
):
    event_id, _ = await _event_with_owner(db_session)
    scanner = await create_verified_user(db_session)
    await create_staff_assignment(
        db_session, event_id, scanner, StaffRole.EVENT_ADMIN, revoked_at=datetime.now(UTC)
    )
    await db_session.commit()

    response = await client.get(f"/probe/events/{event_id}/checkin", headers=auth_headers(scanner))

    assert response.status_code == 404


async def test_staff_of_another_event_gets_404(client: AsyncClient, db_session: AsyncSession):
    event_id, _ = await _event_with_owner(db_session)
    other_event_id, _ = await _event_with_owner(db_session)
    scanner = await create_verified_user(db_session)
    await create_staff_assignment(db_session, other_event_id, scanner, StaffRole.EVENT_ADMIN)
    await db_session.commit()

    response = await client.get(f"/probe/events/{event_id}/checkin", headers=auth_headers(scanner))

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"


async def test_organizer_of_another_event_gets_404(client: AsyncClient, db_session: AsyncSession):
    event_id, _ = await _event_with_owner(db_session)
    _, other_owner = await _event_with_owner(db_session)
    await db_session.commit()

    response = await client.get(
        f"/probe/events/{event_id}/owner", headers=auth_headers(other_owner)
    )

    assert response.status_code == 404


async def test_unknown_event_gets_404(client: AsyncClient, db_session: AsyncSession):
    user = await create_verified_user(db_session)
    await db_session.commit()

    response = await client.get(f"/probe/events/{uuid.uuid4()}/owner", headers=auth_headers(user))

    assert response.status_code == 404


async def test_platform_admin_passes_only_where_allowed(
    client: AsyncClient, db_session: AsyncSession
):
    event_id, _ = await _event_with_owner(db_session)
    admin = await create_verified_user(db_session, platform_role=PlatformRole.PLATFORM_ADMIN)
    await db_session.commit()
    headers = auth_headers(admin)

    moderation = await client.get(f"/probe/events/{event_id}/moderation", headers=headers)
    checkin = await client.get(f"/probe/events/{event_id}/checkin", headers=headers)

    assert moderation.status_code == 200
    assert moderation.json()["actor_role"] == "platform_admin"
    assert checkin.status_code == 403


async def test_event_role_check_requires_authentication(
    client: AsyncClient, db_session: AsyncSession
):
    event_id, _ = await _event_with_owner(db_session)
    await db_session.commit()

    response = await client.get(f"/probe/events/{event_id}/owner")

    assert response.status_code == 401


async def test_event_role_check_rejects_malformed_event_id(
    client: AsyncClient, db_session: AsyncSession
):
    user = await create_verified_user(db_session)
    await db_session.commit()

    response = await client.get("/probe/events/not-a-uuid/owner", headers=auth_headers(user))

    assert response.status_code == 422
