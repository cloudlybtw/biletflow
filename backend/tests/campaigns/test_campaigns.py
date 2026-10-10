import asyncio
import io
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from PIL import Image
from sqlalchemy import func, select, update

from app.modules.campaigns.models import Campaign, CampaignQR, PromoCode
from app.modules.events.models import Event, EventStatus
from app.modules.history.models import AuditLog
from app.modules.ticketing.models import TicketType
from app.modules.users.models import StaffRole
from tests.factories import (
    auth_headers,
    create_event,
    create_organizer,
    create_staff_assignment,
    create_ticket_type,
    create_verified_user,
)


@pytest.fixture
async def context(db_session):
    owner = await create_verified_user(db_session)
    profile = await create_organizer(db_session, owner)
    event_id = await create_event(db_session, profile, status=EventStatus.PUBLISHED)
    ticket = await create_ticket_type(db_session, event_id, price_amount=101)
    other = await create_ticket_type(db_session, event_id, price_amount=2000)
    await db_session.commit()
    return owner, event_id, ticket, other


def url(context):
    return f"/api/v1/events/{context[1]}/campaigns"


async def campaign(client, context, activate=True, **changes):
    response = await client.post(
        url(context),
        json={"name": "Launch", "discount_type": "percent", "discount_value": 15, **changes},
        headers=auth_headers(context[0]),
    )
    assert response.status_code == 201, response.text
    result = response.json()
    if activate:
        activated = await client.post(
            url(context) + f"/{result['id']}/activate", headers=auth_headers(context[0])
        )
        assert activated.status_code == 200, activated.text
        result = activated.json()
    return result


async def validate(client, context, camp, **overrides):
    data = {
        "code": camp["promo_codes"][0]["code"].lower(),
        "items": [{"ticket_type_id": str(context[2].id), "quantity": 3}],
        **overrides,
    }
    return await client.post(f"/api/v1/events/{context[1]}/promo/validate", json=data)


async def test_campaign_crud_and_state_transitions_are_audited(client, db_session, context):
    camp = await campaign(client, context, activate=False, code="launch-15")
    assert camp["status"] == "draft" and camp["promo_codes"][0]["code"] == "LAUNCH-15"
    path = url(context) + f"/{camp['id']}"
    edit = await client.patch(
        path,
        json={"name": "Launch changed", "ticket_type_ids": [str(context[2].id)]},
        headers=auth_headers(context[0]),
    )
    assert edit.status_code == 200, edit.text
    assert edit.json()["ticket_type_ids"] == [str(context[2].id)]
    assert (await client.get(path, headers=auth_headers(context[0]))).json()[
        "name"
    ] == "Launch changed"
    listing = await client.get(url(context), headers=auth_headers(context[0]), params={"limit": 1})
    assert listing.json()["total"] == 1
    assert listing.json()["items"][0]["ticket_type_ids"] == [str(context[2].id)]
    assert (
        await client.post(path + "/disable", headers=auth_headers(context[0]))
    ).status_code == 409
    assert (
        await client.post(path + "/activate", headers=auth_headers(context[0]))
    ).status_code == 200
    assert (await client.delete(path, headers=auth_headers(context[0]))).status_code == 409
    assert (
        await client.post(path + "/disable", headers=auth_headers(context[0]))
    ).status_code == 200
    assert (
        await client.post(path + "/activate", headers=auth_headers(context[0]))
    ).status_code == 409
    assert (
        await client.patch(path, json={"discount_value": 10}, headers=auth_headers(context[0]))
    ).status_code == 409
    unused = await campaign(client, context, activate=False)
    assert (
        await client.delete(url(context) + f"/{unused['id']}", headers=auth_headers(context[0]))
    ).status_code == 204
    actions = set(
        (
            await db_session.scalars(
                select(AuditLog.action_type).where(AuditLog.event_id == context[1])
            )
        ).all()
    )
    assert {
        "campaign.created",
        "campaign.updated",
        "campaign.active",
        "campaign.disabled",
        "campaign.deleted",
    } <= actions


async def test_preview_scopes_discount_without_claiming_redemption(client, db_session, context):
    camp = await campaign(client, context, ticket_type_ids=[str(context[2].id)], max_redemptions=1)
    for _ in range(2):
        result = await validate(
            client,
            context,
            camp,
            items=[
                {"ticket_type_id": str(context[2].id), "quantity": 3},
                {"ticket_type_id": str(context[3].id), "quantity": 1},
            ],
        )
        assert result.status_code == 200, result.text
        assert result.json()["subtotal_amount"] == 2303
        assert result.json()["eligible_subtotal_amount"] == 303
        assert result.json()["discount_amount"] == 45
        assert result.json()["total_amount"] == 2258
    assert (await db_session.get(Campaign, uuid.UUID(camp["id"]))).redemption_count == 0
    ticket = await db_session.get(TicketType, context[2].id)
    assert ticket.quantity_reserved == ticket.quantity_sold == 0
    bad = await validate(
        client, context, camp, items=[{"ticket_type_id": str(context[3].id), "quantity": 1}]
    )
    assert bad.json()["error"]["code"] == "PROMO_NOT_APPLICABLE"


async def test_fixed_discount_capped_to_eligible_subtotal(client, context):
    camp = await campaign(
        client,
        context,
        discount_type="fixed",
        discount_value=10000,
        ticket_type_ids=[str(context[2].id)],
    )
    result = await validate(client, context, camp)
    assert result.json()["discount_amount"] == 303
    assert result.json()["total_amount"] == 0


@pytest.mark.parametrize(
    "state,expected",
    [
        ("disabled", "PROMO_DISABLED"),
        ("draft", "PROMO_DISABLED"),
        ("expired", "PROMO_EXPIRED"),
        ("past", "PROMO_EXPIRED"),
        ("future", "PROMO_NOT_STARTED"),
        ("exhausted", "PROMO_EXHAUSTED"),
        ("inactive_code", "PROMO_DISABLED"),
    ],
)
async def test_preview_error_states(client, db_session, context, state, expected):
    camp = await campaign(client, context, max_redemptions=1)
    values = (
        {"status": state}
        if state in {"disabled", "draft", "expired"}
        else {"ends_at": datetime.now(UTC) - timedelta(seconds=1)}
        if state == "past"
        else {"starts_at": datetime.now(UTC) + timedelta(days=1)}
        if state == "future"
        else {"redemption_count": 1}
        if state == "exhausted"
        else {}
    )
    if values:
        await db_session.execute(
            update(Campaign).where(Campaign.id == uuid.UUID(camp["id"])).values(**values)
        )
    if state == "inactive_code":
        await db_session.execute(
            update(PromoCode)
            .where(PromoCode.id == uuid.UUID(camp["promo_codes"][0]["id"]))
            .values(is_active=False)
        )
    await db_session.commit()
    response = await validate(client, context, camp)
    assert response.status_code == 400, response.text
    assert response.json()["error"]["code"] == expected


async def test_case_insensitive_custom_codes_unique_across_events(client, db_session, context):
    await campaign(client, context, code="WELCOME")
    another = await create_event(db_session)
    profile_id = (await db_session.get(Event, another)).organizer_profile_id
    from app.modules.organizers.models import OrganizerProfile
    from app.modules.users.models import User

    profile = await db_session.get(OrganizerProfile, profile_id)
    owner = await db_session.get(User, profile.user_id)
    await db_session.commit()
    response = await client.post(
        f"/api/v1/events/{another}/campaigns",
        json={
            "name": "Collision",
            "discount_type": "fixed",
            "discount_value": 100,
            "code": "welcome",
        },
        headers=auth_headers(owner),
    )
    assert response.status_code == 409, response.text
    assert response.json()["error"]["code"] == "PROMO_CODE_TAKEN"
    assert await db_session.scalar(select(func.count()).select_from(Campaign)) == 1


async def test_multiple_codes_qr_resolution_and_atomic_scan_counts(client, db_session, context):
    camp = await campaign(client, context)
    path = url(context) + f"/{camp['id']}"
    code = await client.post(
        path + "/promo-codes", json={"code": "SECOND"}, headers=auth_headers(context[0])
    )
    assert code.status_code == 201
    created = await client.post(
        path + "/qr", json={"promo_code_id": code.json()["id"]}, headers=auth_headers(context[0])
    )
    assert created.status_code == 201, created.text
    qr = created.json()
    assert qr["token"].startswith("bfc_") and qr["label"] == "PROMO"
    assert qr["target_url"].endswith(f"/campaign-links/{qr['token']}")
    responses = await asyncio.gather(
        *[client.get(f"/api/v1/campaign-links/{qr['token']}") for _ in range(10)]
    )
    assert all(r.status_code == 200 for r in responses)
    assert all(r.json()["promo_code"] == "SECOND" for r in responses)
    stored = await db_session.get(CampaignQR, uuid.UUID(qr["id"]))
    assert stored.scan_count == 10
    listed = await client.get(path + "/qr", headers=auth_headers(context[0]))
    assert listed.json()[0]["scan_count"] == 10
    image = await client.get(qr["image_url"], headers=auth_headers(context[0]))
    assert image.status_code == 200, image.text
    assert image.headers["content-type"] == "image/png"
    with Image.open(io.BytesIO(image.content)) as png:
        assert png.height == png.width + 60
        assert png.convert("RGB").getpixel((0, png.height - 1)) == (245, 158, 11)
    assert (await client.get("/api/v1/campaign-links/bft_ticket-token")).status_code == 404
    assert (await client.get("/api/v1/campaign-links/bfc_unknown")).status_code == 404


async def test_qr_link_hidden_for_drafts_private_deleted_and_disabled(client, db_session, context):
    camp = await campaign(client, context)
    qr = (
        await client.post(
            url(context) + f"/{camp['id']}/qr", json={}, headers=auth_headers(context[0])
        )
    ).json()
    for values in [
        {"status": "draft"},
        {"status": "published", "visibility": "private"},
        {"visibility": "public", "deleted_at": datetime.now(UTC)},
    ]:
        await db_session.execute(update(Event).where(Event.id == context[1]).values(**values))
        await db_session.commit()
        assert (await client.get(f"/api/v1/campaign-links/{qr['token']}")).status_code == 404
    await db_session.execute(
        update(Event)
        .where(Event.id == context[1])
        .values(deleted_at=None, status="published", visibility="unlisted")
    )
    await db_session.commit()
    assert (await client.get(f"/api/v1/campaign-links/{qr['token']}")).status_code == 200
    await client.post(url(context) + f"/{camp['id']}/disable", headers=auth_headers(context[0]))
    assert (await client.get(f"/api/v1/campaign-links/{qr['token']}")).json()["error"][
        "code"
    ] == "PROMO_DISABLED"
    stored = await db_session.get(CampaignQR, uuid.UUID(qr["id"]))
    assert stored.scan_count == 1


async def test_permissions_and_cross_event_ids(client, db_session, context):
    camp = await campaign(client, context)
    stranger = await create_verified_user(db_session)
    scanner = await create_verified_user(db_session)
    co = await create_verified_user(db_session)
    await create_staff_assignment(db_session, context[1], scanner, StaffRole.EVENT_ADMIN)
    await create_staff_assignment(db_session, context[1], co, StaffRole.CO_ORGANIZER)
    other_event = await create_event(db_session)
    foreign_type = await create_ticket_type(db_session, other_event)
    await db_session.commit()
    path = url(context) + f"/{camp['id']}"
    for user, expected in [(stranger, 404), (scanner, 403), (co, 200)]:
        assert (await client.get(path, headers=auth_headers(user))).status_code == expected
    assert (await client.get(path)).status_code == 401
    assert (
        await client.get(url(context) + f"/{uuid.uuid4()}", headers=auth_headers(context[0]))
    ).status_code == 404
    assert (
        await client.post(
            url(context),
            json={
                "name": "Wrong",
                "discount_type": "fixed",
                "discount_value": 100,
                "ticket_type_ids": [str(foreign_type.id)],
            },
            headers=auth_headers(context[0]),
        )
    ).status_code == 422
    bad_cart = await validate(
        client, context, camp, items=[{"ticket_type_id": str(foreign_type.id), "quantity": 1}]
    )
    assert bad_cart.json()["error"]["code"] == "PROMO_NOT_APPLICABLE"
    assert (
        await client.post(
            f"/api/v1/events/{other_event}/promo/validate",
            json={
                "code": camp["promo_codes"][0]["code"],
                "items": [{"ticket_type_id": str(foreign_type.id), "quantity": 1}],
            },
        )
    ).status_code == 404


@pytest.mark.parametrize(
    "data",
    [
        {"discount_value": 101},
        {"discount_value": 0},
        {"discount_value": None},
        {"discount_type": None},
        {"ticket_type_ids": None},
        {"name": "  "},
        {"starts_at": "2030-01-02T00:00:00Z", "ends_at": "2030-01-01T00:00:00Z"},
        {"max_redemptions": 0},
        {"status": "active"},
    ],
)
async def test_invalid_partial_updates(client, context, data):
    camp = await campaign(client, context)
    response = await client.patch(
        url(context) + f"/{camp['id']}", json=data, headers=auth_headers(context[0])
    )
    assert response.status_code == 422, response.text


async def test_cannot_lower_limit_below_redemption_count(client, db_session, context):
    camp = await campaign(client, context, max_redemptions=3)
    await db_session.execute(
        update(Campaign).where(Campaign.id == uuid.UUID(camp["id"])).values(redemption_count=2)
    )
    await db_session.commit()
    response = await client.patch(
        url(context) + f"/{camp['id']}",
        json={"max_redemptions": 1},
        headers=auth_headers(context[0]),
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "LIMIT_BELOW_REDEMPTIONS"


async def test_duplicate_event_does_not_copy_campaigns(client, context):
    await campaign(client, context)
    response = await client.post(
        f"/api/v1/events/{context[1]}/duplicate", headers=auth_headers(context[0])
    )
    assert response.status_code == 201
    copy = response.json()
    assert (
        await client.get(f"/api/v1/events/{copy['id']}/campaigns", headers=auth_headers(context[0]))
    ).json()["total"] == 0


async def test_cart_quantities_duplicate_lines_and_hidden_types(client, db_session, context):
    camp = await campaign(client, context)
    for items in [
        [{"ticket_type_id": str(context[2].id), "quantity": 0}],
        [{"ticket_type_id": str(context[2].id), "quantity": 1}] * 2,
    ]:
        assert (await validate(client, context, camp, items=items)).status_code == 422
    assert (
        await validate(
            client, context, camp, items=[{"ticket_type_id": str(context[2].id), "quantity": 11}]
        )
    ).json()["error"]["code"] == "INVALID_CART"
    await db_session.execute(
        update(TicketType).where(TicketType.id == context[2].id).values(is_hidden=True)
    )
    await db_session.commit()
    assert (await validate(client, context, camp)).json()["error"]["code"] == "PROMO_NOT_APPLICABLE"


@pytest.mark.parametrize("code", ["bad code", "ab", "_INVALID", "қазақ", "A" * 41])
async def test_invalid_custom_codes(client, context, code):
    response = await client.post(
        url(context),
        json={"name": "Invalid", "discount_type": "percent", "discount_value": 10, "code": code},
        headers=auth_headers(context[0]),
    )
    assert response.status_code == 422, response.text


async def test_qr_cannot_reference_other_campaigns_code(client, context):
    first = await campaign(client, context)
    second = await campaign(client, context)
    response = await client.post(
        url(context) + f"/{first['id']}/qr",
        headers=auth_headers(context[0]),
        json={"promo_code_id": second["promo_codes"][0]["id"]},
    )
    assert response.status_code == 404


async def test_generated_promo_collision_retries(client, context, monkeypatch):
    await campaign(client, context, code="BF-AAAAAAAAAA")
    calls = 0

    def choice(alphabet):
        nonlocal calls
        calls += 1
        return "A" if calls <= 10 else "B"

    monkeypatch.setattr("app.modules.campaigns.service.secrets.choice", choice)
    created = await campaign(client, context)
    assert created["promo_codes"][0]["code"] == "BF-BBBBBBBBBB"
