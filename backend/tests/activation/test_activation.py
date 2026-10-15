import asyncio
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select, update

from app.db.settings import PlatformSetting
from app.modules.activation.models import PaidSalesActivation
from app.modules.events.models import Event, EventStatus
from app.modules.history.models import AuditLog
from app.modules.notifications.models import Notification
from app.modules.organizers.models import OrganizerProfile
from app.modules.payments.models import Payment
from app.modules.users.models import StaffRole
from tests.factories import (
    auth_headers,
    create_event,
    create_organizer,
    create_payout_account,
    create_staff_assignment,
    create_ticket_type,
)


async def post(client, ctx, suffix, data=None, user=None):
    return await client.post(ctx.path + suffix, headers=auth_headers(user or ctx.owner), json=data)


async def prepare(client, db_session, ctx, *, accept=True):
    response = await client.post(
        "/api/v1/organizers/me/identity-verification", headers=auth_headers(ctx.owner)
    )
    # Use the public M1 APIs, so integration tests do not enable activation in SQL.
    assert response.status_code == 200, response.text
    response = await client.post(
        "/api/v1/organizers/me/payout-accounts",
        headers=auth_headers(ctx.owner),
        json={"account_holder_name": "Organizer", "external_account_ref": "KZ1234567890"},
    )
    assert response.status_code == 201, response.text
    if accept:
        assert (await post(client, ctx, "/terms", {"accepted": True})).status_code == 200
    payment = await post(client, ctx, "/pay")
    assert payment.status_code == 201, payment.text
    payment_id = payment.json()["id"]
    success = await client.post(
        f"/api/v1/payments/{payment_id}/simulate",
        headers=auth_headers(ctx.owner),
        json={"outcome": "success"},
    )
    assert success.status_code == 200, success.text
    return payment_id


async def test_checklist_is_read_only_and_reports_each_requirement(client, db_session, ctx):
    result = await client.get(ctx.path + "/checklist", headers=auth_headers(ctx.owner))
    assert result.status_code == 200, result.text
    data = result.json()
    assert data["has_paid_ticket_type"]
    assert data["fee_amount"] == 5000 and data["currency"] == "KZT" and data["simulated"]
    assert all(
        not data[key]
        for key in [
            "identity_verified",
            "payout_account_active",
            "fee_paid",
            "terms_accepted",
            "ready_to_activate",
        ]
    )
    assert await db_session.scalar(select(func.count()).select_from(PaidSalesActivation)) == 0


async def test_full_activation_is_event_scoped_and_idempotent(client, db_session, ctx):
    other_event = await create_event(db_session, ctx.profile, status=EventStatus.PUBLISHED)
    other_ticket = await create_ticket_type(db_session, other_event)
    await db_session.commit()
    cart = {"items": [{"ticket_type_id": str(ctx.ticket.id), "quantity": 1}]}
    before = await client.post(
        f"/api/v1/events/{ctx.event_id}/orders", headers=auth_headers(ctx.other), json=cart
    )
    assert before.status_code == 409 and before.json()["error"]["code"] == "PAID_SALES_INACTIVE"
    payment_id = await prepare(client, db_session, ctx)
    first = await post(client, ctx, "/activate", {})
    assert first.status_code == 200, first.text
    assert first.json()["paid_sales_status"] == first.json()["status"] == "active"
    assert all(
        first.json()[k]
        for k in [
            "has_paid_ticket_type",
            "identity_verified",
            "payout_account_active",
            "fee_paid",
            "terms_accepted",
        ]
    )
    again = await post(client, ctx, "/activate", {})
    assert again.json()["activation_id"] == first.json()["activation_id"]
    assert again.json()["activated_at"] == first.json()["activated_at"]
    assert (await post(client, ctx, "/pay")).json()["id"] == payment_id
    assert (
        await client.post(
            f"/api/v1/events/{ctx.event_id}/orders", headers=auth_headers(ctx.other), json=cart
        )
    ).status_code == 201
    blocked = await client.post(
        f"/api/v1/events/{other_event}/orders",
        headers=auth_headers(ctx.other),
        json={"items": [{"ticket_type_id": str(other_ticket.id), "quantity": 1}]},
    )
    assert blocked.status_code == 409
    assert await db_session.scalar(select(func.count()).select_from(Payment)) == 1
    actions = (await db_session.scalars(select(AuditLog.action_type))).all()
    assert actions.count("paid_sales.activated") == 1
    assert "paid_sales.terms_accepted" in actions and "activation_fee.succeeded" in actions


async def test_incomplete_activation_lists_missing_requirements(client, ctx):
    assert (await post(client, ctx, "/terms", {"accepted": True})).status_code == 200
    result = await post(client, ctx, "/activate", {})
    assert result.status_code == 409
    assert set(result.json()["error"]["details"]["missing"]) == {
        "identity_verified",
        "payout_account_active",
        "fee_paid",
    }
    assert (await post(client, ctx, "/terms", {"accepted": False})).status_code == 422


async def test_payment_failure_retry_and_callback_replay(client, db_session, ctx):
    first = (await post(client, ctx, "/pay")).json()
    assert first["purpose"] == "activation_fee" and first["order_id"] is None
    assert (await post(client, ctx, "/pay")).json()["id"] == first["id"]
    url = f"/api/v1/payments/{first['id']}/simulate"
    failure = await client.post(url, headers=auth_headers(ctx.owner), json={"outcome": "failure"})
    assert failure.status_code == 200 and failure.json()["status"] == "failed"
    assert (
        await client.post(url, headers=auth_headers(ctx.owner), json={"outcome": "failure"})
    ).status_code == 200
    assert (
        await client.post(url, headers=auth_headers(ctx.owner), json={"outcome": "success"})
    ).status_code == 409
    second = (await post(client, ctx, "/pay")).json()
    assert second["id"] != first["id"]
    success_url = f"/api/v1/payments/{second['id']}/simulate"
    responses = await asyncio.gather(
        *[
            client.post(success_url, headers=auth_headers(ctx.owner), json={"outcome": "success"})
            for _ in range(2)
        ]
    )
    assert [r.status_code for r in responses] == [200, 200]
    assert (await client.get(ctx.path + "/checklist", headers=auth_headers(ctx.owner))).json()[
        "fee_paid"
    ]
    assert (
        await db_session.scalar(
            select(func.count())
            .select_from(AuditLog)
            .where(AuditLog.action_type == "activation_fee.succeeded")
        )
        == 1
    )
    assert (
        await db_session.scalar(
            select(func.count())
            .select_from(Notification)
            .where(Notification.type == "payment_failed")
        )
        == 1
    )


async def test_terms_and_fee_are_independent_requirements(client, db_session, ctx):
    await prepare(client, db_session, ctx, accept=False)
    result = await post(client, ctx, "/activate", {})
    assert result.status_code == 409 and result.json()["error"]["details"]["missing"] == [
        "terms_accepted"
    ]
    accepted = await post(client, ctx, "/terms", {"accepted": True})
    repeated = await post(client, ctx, "/terms", {"accepted": True})
    assert repeated.json()["terms_accepted_at"] == accepted.json()["terms_accepted_at"]
    assert (await post(client, ctx, "/activate", {})).status_code == 200


async def test_activation_and_fee_payment_roll_back_when_audit_fails(
    client, db_session, ctx, monkeypatch
):
    from app.modules.activation import service

    async def fail(*args, **kwargs):
        raise RuntimeError("Audit failure")

    monkeypatch.setattr(service, "audit", fail)
    result = await post(client, ctx, "/pay")
    assert result.status_code == 500
    assert await db_session.scalar(select(func.count()).select_from(Payment)) == 0
    assert await db_session.scalar(select(func.count()).select_from(PaidSalesActivation)) == 0
    assert (
        await db_session.get(Event, ctx.event_id, populate_existing=True)
    ).paid_sales_status == "disabled"


async def test_unverified_or_suspended_owner_cannot_accept_terms(client, db_session, ctx):
    from app.modules.users.models import User

    await db_session.execute(
        update(User).where(User.id == ctx.owner.id).values(email_verified_at=None)
    )
    await db_session.commit()
    assert (await post(client, ctx, "/terms", {"accepted": True})).json()["error"][
        "code"
    ] == "EMAIL_NOT_VERIFIED"
    await db_session.execute(update(User).where(User.id == ctx.owner.id).values(status="suspended"))
    await db_session.commit()
    assert (await post(client, ctx, "/pay")).json()["error"]["code"] == "ACCOUNT_SUSPENDED"


async def test_concurrent_payment_and_activation_requests_create_one_record(
    client, db_session, ctx
):
    await db_session.execute(
        update(OrganizerProfile)
        .where(OrganizerProfile.id == ctx.profile.id)
        .values(verification_status="verified", verified_at=datetime.now(UTC))
    )
    await create_payout_account(db_session, ctx.profile)
    await db_session.commit()
    assert (await post(client, ctx, "/terms", {"accepted": True})).status_code == 200
    attempts = await asyncio.gather(*[post(client, ctx, "/pay") for _ in range(3)])
    assert all(r.status_code == 201 for r in attempts), [r.text for r in attempts]
    assert len({r.json()["id"] for r in attempts}) == 1
    payment_id = attempts[0].json()["id"]
    assert (
        await client.post(
            f"/api/v1/payments/{payment_id}/simulate",
            headers=auth_headers(ctx.owner),
            json={"outcome": "success"},
        )
    ).status_code == 200
    activated = await asyncio.gather(*[post(client, ctx, "/activate", {}) for _ in range(3)])
    assert all(r.status_code == 200 for r in activated), [r.text for r in activated]
    assert await db_session.scalar(select(func.count()).select_from(PaidSalesActivation)) == 1
    assert await db_session.scalar(select(func.count()).select_from(Payment)) == 1


@pytest.mark.parametrize("value", [-1, True, "NaN", "Infinity", 1.5, None, "9223372036854775808"])
async def test_invalid_fee_settings_never_create_a_payment(client, db_session, ctx, value):
    await db_session.execute(
        update(PlatformSetting)
        .where(PlatformSetting.key == "activation_fee_kzt")
        .values(value=value)
    )
    await db_session.commit()
    result = await post(client, ctx, "/pay")
    assert result.status_code == 503, result.text
    assert await db_session.scalar(select(func.count()).select_from(Payment)) == 0


async def test_fee_snapshot_and_zero_fee(client, db_session, ctx):
    await db_session.execute(
        update(PlatformSetting).where(PlatformSetting.key == "activation_fee_kzt").values(value=0)
    )
    await db_session.commit()
    result = await post(client, ctx, "/pay")
    assert (
        result.status_code == 201
        and result.json()["amount"] == 0
        and result.json()["status"] == "succeeded"
    )
    await db_session.execute(
        update(PlatformSetting)
        .where(PlatformSetting.key == "activation_fee_kzt")
        .values(value=9000)
    )
    await db_session.commit()
    checklist = (await client.get(ctx.path + "/checklist", headers=auth_headers(ctx.owner))).json()
    assert checklist["fee_paid"] and checklist["fee_amount"] == 0
    assert (await post(client, ctx, "/pay")).json()["id"] == result.json()["id"]


@pytest.mark.parametrize(
    "role", [None, StaffRole.CO_ORGANIZER, StaffRole.EVENT_ADMIN, StaffRole.SUPPORT_AGENT]
)
async def test_only_owner_can_activate_or_simulate_fee(client, db_session, ctx, role):
    if role:
        await create_staff_assignment(db_session, ctx.event_id, ctx.other, role)
        await db_session.commit()
    for suffix, data in [("/terms", {"accepted": True}), ("/pay", None), ("/activate", {})]:
        response = await post(client, ctx, suffix, data, ctx.other)
        assert response.status_code in {403, 404}
    payment = await post(client, ctx, "/pay")
    response = await client.post(
        f"/api/v1/payments/{payment.json()['id']}/simulate",
        headers=auth_headers(ctx.other),
        json={"outcome": "success"},
    )
    assert response.status_code == 404


async def test_payout_must_belong_to_owner_and_cannot_change_after_activation(
    client, db_session, ctx
):
    await prepare(client, db_session, ctx)
    other_profile = await create_organizer(db_session, ctx.other)
    foreign = await create_payout_account(db_session, other_profile)
    await db_session.commit()
    invalid = await post(client, ctx, "/activate", {"payout_account_id": str(foreign.id)})
    assert invalid.status_code == 409
    valid = await post(client, ctx, "/activate", {})
    assert valid.status_code == 200
    another = await create_payout_account(db_session, ctx.profile)
    await db_session.commit()
    assert (await post(client, ctx, "/activate", {"payout_account_id": str(another.id)})).json()[
        "error"
    ]["code"] == "ACTIVATION_PAYOUT_LOCKED"


@pytest.mark.parametrize("target", ["cancelled", "ended", "deleted", "suspended"])
async def test_activation_rejects_unavailable_events(client, db_session, ctx, target):
    values = {
        "cancelled": {"status": "cancelled"},
        "ended": {
            "starts_at": datetime.now(UTC) - timedelta(days=2),
            "ends_at": datetime.now(UTC) - timedelta(days=1),
        },
        "deleted": {"deleted_at": datetime.now(UTC)},
        "suspended": {"is_suspended": True},
    }[target]
    await db_session.execute(update(Event).where(Event.id == ctx.event_id).values(**values))
    await db_session.commit()
    result = await post(client, ctx, "/pay")
    assert result.status_code == (404 if target == "deleted" else 409), result.text


async def test_no_paid_types_cannot_charge_fee(client, db_session, ctx):
    from app.modules.ticketing.models import TicketType

    await db_session.execute(
        update(TicketType).where(TicketType.id == ctx.ticket.id).values(price_amount=0)
    )
    await db_session.commit()
    assert (await post(client, ctx, "/pay")).json()["error"]["code"] == "NO_PAID_TICKET_TYPE"
    assert await db_session.scalar(select(func.count()).select_from(Payment)) == 0
