import asyncio
import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.history.models import AuditLog
from app.modules.organizers.models import OrganizerProfile, PayoutAccount, PayoutAccountStatus
from app.modules.users.models import User
from tests.factories import (
    auth_headers,
    create_organizer,
    create_payout_account,
    create_verified_user,
)

URL = "/api/v1/organizers/me/payout-accounts"


def _body(ref: str = "KZ86 125K ZT50 0410 0100", **overrides) -> dict:
    return {"account_holder_name": "Aigerim Sadykova", "external_account_ref": ref} | overrides


async def _organizer(session: AsyncSession) -> tuple[User, OrganizerProfile]:
    user = await create_verified_user(session)
    profile = await create_organizer(session, user=user)
    await session.commit()
    return user, profile


async def _accounts(session: AsyncSession, profile: OrganizerProfile) -> list[PayoutAccount]:
    result = await session.scalars(
        select(PayoutAccount)
        .where(PayoutAccount.organizer_profile_id == profile.id)
        .order_by(PayoutAccount.created_at)
        .execution_options(populate_existing=True)
    )
    return list(result.all())


# --- add --------------------------------------------------------------------


async def test_first_payout_account_is_simulated_active_and_default(
    client: AsyncClient, db_session: AsyncSession
):
    user, profile = await _organizer(db_session)

    response = await client.post(URL, json=_body(), headers=auth_headers(user))

    assert response.status_code == 201
    data = response.json()
    assert data["provider"] == "biletflow_sim"
    assert data["external_account_ref"] == "KZ86125KZT5004100100"
    assert data["currency"] == "KZT"
    assert data["status"] == "active"
    assert data["is_default"] is True
    assert data["simulated"] is True
    (account,) = await _accounts(db_session, profile)
    assert account.is_simulated is True
    row = await db_session.scalar(
        select(AuditLog).where(AuditLog.action_type == "payout_account.added")
    )
    assert row.entity_id == data["id"]
    assert row.actor_user_id == user.id
    assert row.metadata_["simulated"] is True


async def test_second_payout_account_is_not_default(client: AsyncClient, db_session: AsyncSession):
    user, profile = await _organizer(db_session)
    await client.post(URL, json=_body("KZ000000000000000001"), headers=auth_headers(user))

    response = await client.post(
        URL, json=_body("KZ000000000000000002"), headers=auth_headers(user)
    )

    assert response.json()["is_default"] is False
    assert [a.is_default for a in await _accounts(db_session, profile)] == [True, False]


async def test_concurrent_first_accounts_get_exactly_one_default(
    client: AsyncClient, db_session: AsyncSession
):
    user, profile = await _organizer(db_session)
    headers = auth_headers(user)

    responses = await asyncio.gather(
        *(
            client.post(URL, json=_body(f"KZ00000000000000000{i}"), headers=headers)
            for i in range(5)
        )
    )

    assert [r.status_code for r in responses] == [201] * 5
    assert sum(a.is_default for a in await _accounts(db_session, profile)) == 1


async def test_duplicate_payout_account_returns_409(client: AsyncClient, db_session: AsyncSession):
    user, _ = await _organizer(db_session)
    # Spaces and case are normalized away, so this is the same account.
    await client.post(URL, json=_body("kz 1111"), headers=auth_headers(user))

    response = await client.post(URL, json=_body("KZ1111"), headers=auth_headers(user))

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "PAYOUT_ACCOUNT_EXISTS"


@pytest.mark.parametrize(
    "body",
    [
        _body("KZ1"),
        _body("KZ86-125K"),
        _body("K" * 35),
        _body(account_holder_name=" "),
        {"account_holder_name": "X"},
    ],
)
async def test_add_payout_account_invalid_input_returns_422_envelope(
    client: AsyncClient, db_session: AsyncSession, body
):
    user, _ = await _organizer(db_session)

    response = await client.post(URL, json=body, headers=auth_headers(user))

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


async def test_add_payout_account_requires_organizer_profile(
    client: AsyncClient, db_session: AsyncSession
):
    user = await create_verified_user(db_session)
    await db_session.commit()

    response = await client.post(URL, json=_body(), headers=auth_headers(user))

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "ORGANIZER_PROFILE_NOT_FOUND"


async def test_add_payout_account_requires_authentication(client: AsyncClient):
    response = await client.post(URL, json=_body())

    assert response.status_code == 401


# --- list -------------------------------------------------------------------


async def test_list_payout_accounts_is_paginated_and_scoped_to_owner(
    client: AsyncClient, db_session: AsyncSession
):
    user, profile = await _organizer(db_session)
    _, other = await _organizer(db_session)
    mine = [await create_payout_account(db_session, profile) for _ in range(3)]
    await create_payout_account(db_session, other)
    await db_session.commit()

    first_page = await client.get(URL, params={"limit": 2}, headers=auth_headers(user))
    second_page = await client.get(
        URL, params={"limit": 2, "offset": 2}, headers=auth_headers(user)
    )

    assert first_page.status_code == 200
    assert first_page.json()["total"] == 3
    ids = [a["id"] for a in first_page.json()["items"] + second_page.json()["items"]]
    assert sorted(ids) == sorted(str(a.id) for a in mine)
    assert all(a["simulated"] is True for a in first_page.json()["items"])


@pytest.mark.parametrize("params", [{"limit": 0}, {"limit": 101}, {"offset": -1}])
async def test_list_payout_accounts_rejects_bad_pagination(
    client: AsyncClient, db_session: AsyncSession, params
):
    user, _ = await _organizer(db_session)

    response = await client.get(URL, params=params, headers=auth_headers(user))

    assert response.status_code == 422


async def test_list_payout_accounts_requires_organizer_profile(
    client: AsyncClient, db_session: AsyncSession
):
    user = await create_verified_user(db_session)
    await db_session.commit()

    response = await client.get(URL, headers=auth_headers(user))

    assert response.status_code == 404


async def test_list_payout_accounts_requires_authentication(client: AsyncClient):
    response = await client.get(URL)

    assert response.status_code == 401


# --- set default ------------------------------------------------------------


async def test_set_default_moves_the_default_flag_and_audits(
    client: AsyncClient, db_session: AsyncSession
):
    user, profile = await _organizer(db_session)
    first = await create_payout_account(db_session, profile, is_default=True)
    second = await create_payout_account(db_session, profile)
    await db_session.commit()

    response = await client.post(f"{URL}/{second.id}/default", headers=auth_headers(user))

    assert response.status_code == 200
    assert response.json()["is_default"] is True
    defaults = {a.id: a.is_default for a in await _accounts(db_session, profile)}
    assert defaults == {first.id: False, second.id: True}
    row = await db_session.scalar(
        select(AuditLog).where(AuditLog.action_type == "payout_account.default_set")
    )
    assert row.entity_id == str(second.id)


async def test_set_default_on_current_default_is_a_no_op(
    client: AsyncClient, db_session: AsyncSession
):
    user, profile = await _organizer(db_session)
    account = await create_payout_account(db_session, profile, is_default=True)
    await db_session.commit()

    response = await client.post(f"{URL}/{account.id}/default", headers=auth_headers(user))

    assert response.status_code == 200
    assert response.json()["is_default"] is True


async def test_concurrent_set_default_leaves_exactly_one_default(
    client: AsyncClient, db_session: AsyncSession
):
    user, profile = await _organizer(db_session)
    accounts = [await create_payout_account(db_session, profile) for _ in range(4)]
    await db_session.commit()
    headers = auth_headers(user)

    responses = await asyncio.gather(
        *(client.post(f"{URL}/{a.id}/default", headers=headers) for a in accounts)
    )

    assert [r.status_code for r in responses] == [200] * 4
    assert sum(a.is_default for a in await _accounts(db_session, profile)) == 1


async def test_disabled_account_cannot_be_default(client: AsyncClient, db_session: AsyncSession):
    user, profile = await _organizer(db_session)
    account = await create_payout_account(db_session, profile, status=PayoutAccountStatus.DISABLED)
    await db_session.commit()

    response = await client.post(f"{URL}/{account.id}/default", headers=auth_headers(user))

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "PAYOUT_ACCOUNT_NOT_ACTIVE"


async def test_cannot_set_default_on_another_organizers_account(
    client: AsyncClient, db_session: AsyncSession
):
    user, _ = await _organizer(db_session)
    _, other = await _organizer(db_session)
    theirs = await create_payout_account(db_session, other)
    await db_session.commit()

    response = await client.post(f"{URL}/{theirs.id}/default", headers=auth_headers(user))

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"
    await db_session.refresh(theirs)
    assert theirs.is_default is False


async def test_set_default_on_unknown_account_returns_404(
    client: AsyncClient, db_session: AsyncSession
):
    user, _ = await _organizer(db_session)

    response = await client.post(f"{URL}/{uuid.uuid4()}/default", headers=auth_headers(user))

    assert response.status_code == 404


async def test_set_default_requires_authentication(client: AsyncClient):
    response = await client.post(f"{URL}/{uuid.uuid4()}/default")

    assert response.status_code == 401
