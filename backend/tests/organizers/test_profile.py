import asyncio

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.history.models import AuditLog
from app.modules.organizers.models import OrganizerProfile
from tests.factories import auth_headers, create_organizer, create_user, create_verified_user

URL = "/api/v1/organizers/me"
VERIFY_URL = f"{URL}/identity-verification"


async def _audit_rows(session: AsyncSession, action_type: str) -> list[AuditLog]:
    result = await session.scalars(select(AuditLog).where(AuditLog.action_type == action_type))
    return list(result.all())


# --- create -----------------------------------------------------------------


async def test_become_organizer_creates_profile(client: AsyncClient, db_session: AsyncSession):
    user = await create_verified_user(db_session)
    await db_session.commit()

    response = await client.post(
        URL,
        json={
            "display_name": "  Almaty Jazz Club ",
            "contact_phone": "+77271234567",
            "description": "Live jazz every Friday.",
        },
        headers=auth_headers(user),
    )

    assert response.status_code == 201
    data = response.json()
    assert data["user_id"] == str(user.id)
    assert data["display_name"] == "Almaty Jazz Club"
    assert data["contact_email"] == user.email
    assert data["contact_phone"] == "+77271234567"
    assert data["verification_status"] == "unverified"
    assert data["verified_at"] is None
    me = await client.get("/api/v1/me", headers=auth_headers(user))
    assert me.json()["is_organizer"] is True


async def test_become_organizer_is_audited(client: AsyncClient, db_session: AsyncSession):
    user = await create_verified_user(db_session)
    await db_session.commit()

    response = await client.post(URL, json={"display_name": "Org"}, headers=auth_headers(user))

    (row,) = await _audit_rows(db_session, "organizer_profile.created")
    assert row.actor_user_id == user.id
    assert row.actor_role == "organizer"
    assert row.entity_type == "organizer_profile"
    assert row.entity_id == response.json()["id"]


async def test_become_organizer_accepts_separate_contact_email(
    client: AsyncClient, db_session: AsyncSession
):
    user = await create_verified_user(db_session)
    await db_session.commit()

    response = await client.post(
        URL,
        json={"display_name": "Org", "contact_email": "events@example.com"},
        headers=auth_headers(user),
    )

    assert response.json()["contact_email"] == "events@example.com"


async def test_become_organizer_requires_verified_email(
    client: AsyncClient, db_session: AsyncSession
):
    user = await create_user(db_session)
    await db_session.commit()

    response = await client.post(URL, json={"display_name": "Org"}, headers=auth_headers(user))

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "EMAIL_NOT_VERIFIED"
    assert (await db_session.scalars(select(OrganizerProfile))).all() == []


async def test_become_organizer_twice_returns_409(client: AsyncClient, db_session: AsyncSession):
    user = await create_verified_user(db_session)
    await create_organizer(db_session, user=user)
    await db_session.commit()

    response = await client.post(URL, json={"display_name": "Again"}, headers=auth_headers(user))

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "ORGANIZER_PROFILE_EXISTS"


async def test_concurrent_become_organizer_creates_one_profile(
    client: AsyncClient, db_session: AsyncSession
):
    user = await create_verified_user(db_session)
    await db_session.commit()
    headers = auth_headers(user)

    responses = await asyncio.gather(
        *(client.post(URL, json={"display_name": f"Org {i}"}, headers=headers) for i in range(5))
    )

    assert sorted(r.status_code for r in responses) == [201, 409, 409, 409, 409]
    assert len((await db_session.scalars(select(OrganizerProfile))).all()) == 1
    assert len(await _audit_rows(db_session, "organizer_profile.created")) == 1


@pytest.mark.parametrize(
    "body",
    [{}, {"display_name": "  "}, {"display_name": "Org", "contact_email": "nope"}],
)
async def test_become_organizer_invalid_input_returns_422_envelope(
    client: AsyncClient, db_session: AsyncSession, body
):
    user = await create_verified_user(db_session)
    await db_session.commit()

    response = await client.post(URL, json=body, headers=auth_headers(user))

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


async def test_become_organizer_requires_authentication(client: AsyncClient):
    response = await client.post(URL, json={"display_name": "Org"})

    assert response.status_code == 401


# --- view / update ----------------------------------------------------------


async def test_get_my_organizer_profile(client: AsyncClient, db_session: AsyncSession):
    user = await create_verified_user(db_session)
    profile = await create_organizer(db_session, user=user, display_name="Steppe Events")
    await db_session.commit()

    response = await client.get(URL, headers=auth_headers(user))

    assert response.status_code == 200
    assert response.json()["id"] == str(profile.id)
    assert response.json()["display_name"] == "Steppe Events"


async def test_get_organizer_profile_when_not_organizer_returns_404(
    client: AsyncClient, db_session: AsyncSession
):
    user = await create_verified_user(db_session)
    await db_session.commit()

    response = await client.get(URL, headers=auth_headers(user))

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "ORGANIZER_PROFILE_NOT_FOUND"


async def test_get_organizer_profile_requires_authentication(client: AsyncClient):
    response = await client.get(URL)

    assert response.status_code == 401


async def test_update_organizer_profile_changes_sent_fields_and_audits(
    client: AsyncClient, db_session: AsyncSession
):
    user = await create_verified_user(db_session)
    profile = await create_organizer(
        db_session, user=user, display_name="Old", contact_phone="+77000000000"
    )
    await db_session.commit()

    response = await client.patch(
        URL,
        json={"display_name": "New", "description": "About us", "contact_phone": None},
        headers=auth_headers(user),
    )

    assert response.status_code == 200
    data = response.json()
    assert data["display_name"] == "New"
    assert data["description"] == "About us"
    assert data["contact_phone"] is None
    assert data["contact_email"] == profile.contact_email
    (row,) = await _audit_rows(db_session, "organizer_profile.updated")
    assert row.entity_id == str(profile.id)
    assert row.metadata_["changes"]["display_name"] == {"from": "Old", "to": "New"}
    assert set(row.metadata_["changes"]) == {"display_name", "description", "contact_phone"}


async def test_update_organizer_profile_without_changes_writes_no_audit(
    client: AsyncClient, db_session: AsyncSession
):
    user = await create_verified_user(db_session)
    await create_organizer(db_session, user=user, display_name="Same")
    await db_session.commit()

    response = await client.patch(URL, json={"display_name": "Same"}, headers=auth_headers(user))

    assert response.status_code == 200
    assert await _audit_rows(db_session, "organizer_profile.updated") == []


@pytest.mark.parametrize("body", [{"display_name": None}, {"contact_email": None}])
async def test_update_organizer_profile_rejects_null_required_fields(
    client: AsyncClient, db_session: AsyncSession, body
):
    user = await create_verified_user(db_session)
    await create_organizer(db_session, user=user)
    await db_session.commit()

    response = await client.patch(URL, json=body, headers=auth_headers(user))

    assert response.status_code == 422


async def test_update_organizer_profile_when_not_organizer_returns_404(
    client: AsyncClient, db_session: AsyncSession
):
    user = await create_verified_user(db_session)
    await db_session.commit()

    response = await client.patch(URL, json={"display_name": "X"}, headers=auth_headers(user))

    assert response.status_code == 404


# --- simulated identity verification ----------------------------------------


async def test_identity_verification_marks_profile_verified(
    client: AsyncClient, db_session: AsyncSession
):
    user = await create_verified_user(db_session)
    profile = await create_organizer(db_session, user=user)
    await db_session.commit()

    response = await client.post(VERIFY_URL, headers=auth_headers(user))

    assert response.status_code == 200
    data = response.json()
    assert data["verification_status"] == "verified"
    assert data["verified_at"] is not None
    assert data["simulated"] is True
    await db_session.refresh(profile)
    assert profile.verification_status == "verified"
    (row,) = await _audit_rows(db_session, "organizer_profile.identity_verified")
    assert row.entity_id == str(profile.id)
    assert row.metadata_ == {"simulated": True}


async def test_identity_verification_is_idempotent(client: AsyncClient, db_session: AsyncSession):
    user = await create_verified_user(db_session)
    await create_organizer(db_session, user=user)
    await db_session.commit()
    first = await client.post(VERIFY_URL, headers=auth_headers(user))

    second = await client.post(VERIFY_URL, headers=auth_headers(user))

    assert second.status_code == 200
    assert second.json()["verified_at"] == first.json()["verified_at"]
    assert len(await _audit_rows(db_session, "organizer_profile.identity_verified")) == 1


async def test_identity_verification_requires_organizer_profile(
    client: AsyncClient, db_session: AsyncSession
):
    user = await create_verified_user(db_session)
    await db_session.commit()

    response = await client.post(VERIFY_URL, headers=auth_headers(user))

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "ORGANIZER_PROFILE_NOT_FOUND"


async def test_identity_verification_requires_authentication(client: AsyncClient):
    response = await client.post(VERIFY_URL)

    assert response.status_code == 401
