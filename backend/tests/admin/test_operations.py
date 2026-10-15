import asyncio
import csv
import io
import uuid
from datetime import datetime

import pytest
from sqlalchemy import func, select, update

from app.db.settings import PlatformSetting
from app.modules.auth.models import UserToken, UserTokenPurpose
from app.modules.history.models import AuditLog
from app.modules.orders.models import Order
from app.modules.users.models import User, UserStatus
from tests.factories import (
    DEFAULT_PASSWORD,
    auth_headers,
    complete_purchase,
    create_user_token,
    create_verified_user,
)
from tests.orders.helpers import pay, placed_order, simulate

RESOURCES = ["users", "events", "orders", "payments", "refunds", "activations"]


@pytest.mark.parametrize("resource", RESOURCES)
async def test_admin_list_export_detail_happy_and_permissions(client, reporting_context, resource):
    c = reporting_context
    order = await complete_purchase(client, c)
    await client.post(
        f"/api/v1/events/{c.event_id}/orders/{order['id']}/refunds",
        headers=auth_headers(c.owner),
        json={},
    )
    if resource == "activations":
        terms = await client.post(
            f"/api/v1/events/{c.event_id}/paid-sales/terms",
            headers=auth_headers(c.owner),
            json={"accepted": True},
        )
        assert terms.status_code == 200, terms.text
    headers = auth_headers(c.admin)
    response = await client.get(f"/api/v1/admin/{resource}", headers=headers)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["total"] >= 1
    if body["items"]:
        rid = body["items"][0]["id"]
        detail = await client.get(f"/api/v1/admin/{resource}/{rid}", headers=headers)
        assert detail.status_code == 200, detail.text
        forbidden = await client.get(
            f"/api/v1/admin/{resource}/{rid}", headers=auth_headers(c.owner)
        )
        assert forbidden.status_code == 403
    assert (
        await client.get(f"/api/v1/admin/{resource}/{uuid.uuid4()}", headers=headers)
    ).status_code == 404
    exported = await client.get(f"/api/v1/admin/{resource}/export.csv", headers=headers)
    assert exported.status_code == 200, exported.text
    records = list(csv.DictReader(io.StringIO(exported.content.decode("utf-8-sig"))))
    assert len(records) == body["total"]
    for suffix in ["", "/export.csv"]:
        assert (
            await client.get(f"/api/v1/admin/{resource}{suffix}", headers=auth_headers(c.owner))
        ).status_code == 403
        assert (await client.get(f"/api/v1/admin/{resource}{suffix}")).status_code == 401
    assert "password_hash" not in response.text and "provider_payload" not in response.text


async def test_search_status_dates_event_payment_purpose_and_literal_wildcards(
    client, reporting_context
):
    c = reporting_context
    order = await placed_order(client, c)
    payment = await pay(client, c, order["id"])
    await simulate(client, c, payment["id"], "failure")
    headers = auth_headers(c.admin)
    response = await client.get(
        "/api/v1/admin/payments",
        headers=headers,
        params={
            "status": "failed",
            "event_id": str(c.event_id),
            "purpose": "ticket_purchase",
            "q": order["order_number"],
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()["total"] == 1 and response.json()["items"][0]["simulated"] is True
    response = await client.get("/api/v1/admin/events", headers=headers, params={"q": "%"})
    assert response.json()["total"] == 0
    response = await client.get(
        "/api/v1/admin/users", headers=headers, params={"q": c.buyer.email.upper()}
    )
    assert response.json()["total"] == 1
    assert (
        await client.get("/api/v1/admin/orders", headers=headers, params={"status": "nonsense"})
    ).status_code == 422
    assert (
        await client.get("/api/v1/admin/users", headers=headers, params={"date_from": "2026-01-01"})
    ).status_code == 422
    assert (
        await client.get(
            "/api/v1/admin/payments", headers=headers, params={"date_to": "2000-01-01T00:00:00Z"}
        )
    ).json()["total"] == 0
    assert (
        await client.get("/api/v1/admin/users", headers=headers, params={"offset": 999})
    ).json()["items"] == []


async def test_user_suspension_blocks_access_revokes_tokens_and_is_idempotent(
    client, reporting_context, db_session
):
    c = reporting_context
    raw, token = await create_user_token(db_session, c.buyer, UserTokenPurpose.REFRESH)
    await db_session.commit()
    url = f"/api/v1/admin/users/{c.buyer.id}"
    for _ in range(2):
        response = await client.post(
            url + "/suspend", json={"reason": "Demo moderation"}, headers=auth_headers(c.admin)
        )
        assert response.status_code == 200 and response.json()["status"] == "suspended", (
            response.text
        )
    assert (await client.get("/api/v1/me", headers=auth_headers(c.buyer))).status_code == 403
    await db_session.refresh(token)
    assert token.used_at is not None
    for _ in range(2):
        response = await client.post(url + "/unsuspend", headers=auth_headers(c.admin))
        assert response.status_code == 200 and response.json()["status"] == "active"
    assert (
        await client.post("/api/v1/auth/refresh", json={"refresh_token": raw})
    ).status_code == 401
    assert (
        await client.post(
            "/api/v1/auth/login", json={"email": c.buyer.email, "password": DEFAULT_PASSWORD}
        )
    ).status_code == 200
    actions = list(
        (
            await db_session.scalars(
                select(AuditLog.action_type).where(AuditLog.entity_id == str(c.buyer.id))
            )
        ).all()
    )
    assert actions == ["user.suspended", "user.unsuspended"]


@pytest.mark.parametrize("action", ["suspend", "unsuspend"])
async def test_user_moderation_permissions_deleted_and_missing(
    client, reporting_context, db_session, action
):
    c = reporting_context
    data = {"reason": "Review"} if action == "suspend" else None
    url = f"/api/v1/admin/users/{c.buyer.id}/{action}"
    assert (await client.post(url, json=data, headers=auth_headers(c.owner))).status_code == 403
    assert (await client.post(url, json=data)).status_code == 401
    assert (
        await client.post(
            f"/api/v1/admin/users/{uuid.uuid4()}/{action}", json=data, headers=auth_headers(c.admin)
        )
    ).status_code == 404
    await db_session.execute(
        update(User).where(User.id == c.buyer.id).values(status=UserStatus.DELETED)
    )
    await db_session.commit()
    assert (await client.post(url, json=data, headers=auth_headers(c.admin))).status_code == 409


async def test_admin_cannot_suspend_self_and_concurrent_moderation_writes_one_audit(
    client, reporting_context, db_session
):
    c = reporting_context
    response = await client.post(
        f"/api/v1/admin/users/{c.admin.id}/suspend",
        json={"reason": "Oops"},
        headers=auth_headers(c.admin),
    )
    assert (
        response.status_code == 409 and response.json()["error"]["code"] == "ADMIN_SELF_SUSPENSION"
    )
    results = await asyncio.gather(
        *(
            client.post(
                f"/api/v1/admin/users/{c.buyer.id}/suspend",
                json={"reason": "Review"},
                headers=auth_headers(c.admin),
            )
            for _ in range(2)
        )
    )
    assert [r.status_code for r in results] == [200, 200]
    assert (
        await db_session.scalar(
            select(func.count())
            .select_from(AuditLog)
            .where(AuditLog.action_type == "user.suspended")
        )
        == 1
    )


async def test_suspension_racing_refresh_revokes_every_issued_refresh(
    client, reporting_context, db_session
):
    c = reporting_context
    raw, _ = await create_user_token(db_session, c.buyer, UserTokenPurpose.REFRESH)
    await db_session.commit()
    refresh, suspend = await asyncio.wait_for(
        asyncio.gather(
            client.post("/api/v1/auth/refresh", json={"refresh_token": raw}),
            client.post(
                f"/api/v1/admin/users/{c.buyer.id}/suspend",
                json={"reason": "Review"},
                headers=auth_headers(c.admin),
            ),
        ),
        timeout=5,
    )
    assert suspend.status_code == 200 and refresh.status_code in [200, 401, 403]
    assert (
        await db_session.scalar(
            select(func.count())
            .select_from(UserToken)
            .where(
                UserToken.user_id == c.buyer.id,
                UserToken.purpose == UserTokenPurpose.REFRESH,
                UserToken.used_at.is_(None),
            )
        )
        == 0
    )


async def test_settings_atomic_audited_and_do_not_reprice_existing_orders(
    client, reporting_context, db_session
):
    c = reporting_context
    order = await placed_order(client, c)
    response = await client.patch(
        "/api/v1/admin/settings",
        headers=auth_headers(c.admin),
        json={
            "activation_fee_kzt": 7000,
            "processing_fee_percent": 2.5,
            "order_hold_minutes": 30,
            "seat_hold_minutes": 12,
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()["total"] == 4 and all(
        r["updated_by"] == str(c.admin.id) for r in response.json()["items"]
    )
    repeat = await client.patch(
        "/api/v1/admin/settings", headers=auth_headers(c.admin), json={"order_hold_minutes": 30}
    )
    assert repeat.status_code == 200
    count = await db_session.scalar(
        select(func.count())
        .select_from(AuditLog)
        .where(AuditLog.action_type == "platform_setting.updated")
    )
    assert count == 4
    original = await db_session.get(Order, uuid.UUID(order["id"]))
    assert original.fee_amount == 0 and original.expires_at == datetime.fromisoformat(
        order["expires_at"]
    )
    next_order = await placed_order(client, c)
    assert next_order["fee_amount"] == 25
    assert (await client.get("/api/v1/admin/settings", headers=auth_headers(c.admin))).json()[
        "total"
    ] == 4
    assert (
        await client.get("/api/v1/admin/settings", headers=auth_headers(c.owner))
    ).status_code == 403
    assert (
        await client.patch(
            "/api/v1/admin/settings", headers=auth_headers(c.owner), json={"order_hold_minutes": 20}
        )
    ).status_code == 403


@pytest.mark.parametrize(
    "data",
    [
        {},
        {"unknown": 1},
        {"activation_fee_kzt": -1},
        {"activation_fee_kzt": 1.5},
        {"activation_fee_kzt": True},
        {"activation_fee_kzt": 2**63},
        {"processing_fee_percent": 101},
        {"processing_fee_percent": "2.5"},
        {"order_hold_minutes": 0},
        {"seat_hold_minutes": 10081},
        {"order_hold_minutes": None},
        {"processing_fee_percent": True},
    ],
)
async def test_settings_reject_invalid_values_without_partial_changes(
    client, reporting_context, db_session, data
):
    c = reporting_context
    response = await client.patch(
        "/api/v1/admin/settings",
        headers=auth_headers(c.admin),
        json={"seat_hold_minutes": 11, **data} if data else data,
    )
    assert response.status_code == 422, response.text
    assert (
        await db_session.scalar(
            select(PlatformSetting.value).where(PlatformSetting.key == "seat_hold_minutes")
        )
        == 10
    )


async def test_audit_failure_rolls_back_settings_and_suspension(
    client, reporting_context, db_session, monkeypatch
):
    c = reporting_context
    from app.modules.admin import operations

    async def fail(*args, **kwargs):
        raise RuntimeError("audit failed")

    monkeypatch.setattr(operations.history, "record", fail)
    response = await client.patch(
        "/api/v1/admin/settings",
        headers=auth_headers(c.admin),
        json={"order_hold_minutes": 21, "seat_hold_minutes": 11},
    )
    assert response.status_code == 500
    assert (
        await db_session.scalar(
            select(PlatformSetting.value).where(PlatformSetting.key == "order_hold_minutes")
        )
        == 15
    )
    response = await client.post(
        f"/api/v1/admin/users/{c.buyer.id}/suspend",
        headers=auth_headers(c.admin),
        json={"reason": "Review"},
    )
    assert response.status_code == 500
    await db_session.refresh(c.buyer)
    assert c.buyer.status == "active"


async def test_csv_sanitizes_formula_text_and_does_not_expose_secrets(
    client, reporting_context, db_session
):
    c = reporting_context
    user = await create_verified_user(db_session, full_name="=SUM(A1:A2)")
    await db_session.commit()
    response = await client.get(
        "/api/v1/admin/users/export.csv", headers=auth_headers(c.admin), params={"q": user.email}
    )
    rows = list(csv.DictReader(io.StringIO(response.content.decode("utf-8-sig"))))
    assert rows[0]["full_name"] == "'=SUM(A1:A2)"
    assert "password_hash" not in rows[0]


@pytest.mark.parametrize("value", ["NaN", "Infinity", "-Infinity"])
async def test_settings_nonfinite_json_returns_valid_422(client, reporting_context, value):
    response = await client.patch(
        "/api/v1/admin/settings",
        headers={**auth_headers(reporting_context.admin), "Content-Type": "application/json"},
        content='{"processing_fee_percent":' + value + "}",
    )
    assert response.status_code == 422, response.text
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


async def test_settings_require_authentication_and_concurrent_edits_are_atomic(
    client, reporting_context, db_session
):
    c = reporting_context
    assert (await client.get("/api/v1/admin/settings")).status_code == 401
    assert (
        await client.patch("/api/v1/admin/settings", json={"order_hold_minutes": 20})
    ).status_code == 401
    choices = [
        {"order_hold_minutes": 20, "seat_hold_minutes": 12},
        {"order_hold_minutes": 25, "seat_hold_minutes": 15},
    ]
    results = await asyncio.gather(
        *(
            client.patch("/api/v1/admin/settings", headers=auth_headers(c.admin), json=choice)
            for choice in choices
        )
    )
    assert all(r.status_code == 200 for r in results)
    values = dict(
        (
            await db_session.execute(
                select(PlatformSetting.key, PlatformSetting.value).where(
                    PlatformSetting.key.in_(["order_hold_minutes", "seat_hold_minutes"])
                )
            )
        ).all()
    )
    assert values in choices


async def test_suspension_racing_login_never_leaves_refresh_session(
    client, reporting_context, db_session
):
    c = reporting_context
    login, suspend = await asyncio.wait_for(
        asyncio.gather(
            client.post(
                "/api/v1/auth/login", json={"email": c.buyer.email, "password": DEFAULT_PASSWORD}
            ),
            client.post(
                f"/api/v1/admin/users/{c.buyer.id}/suspend",
                headers=auth_headers(c.admin),
                json={"reason": "Review"},
            ),
        ),
        timeout=5,
    )
    assert suspend.status_code == 200 and login.status_code in [200, 403]
    assert (
        await db_session.scalar(
            select(func.count())
            .select_from(UserToken)
            .where(
                UserToken.user_id == c.buyer.id,
                UserToken.purpose == UserTokenPurpose.REFRESH,
                UserToken.used_at.is_(None),
            )
        )
        == 0
    )


async def test_admin_support_event_order_category_filters_reuse_existing_cases(
    client, reporting_context
):
    c = reporting_context
    from tests.support.helpers import opened_case

    order = await complete_purchase(client, c)
    case = await opened_case(client, c, order_id=order["id"], category="refund")
    await opened_case(client, c, category="event_information")
    response = await client.get(
        "/api/v1/admin/support/cases",
        headers=auth_headers(c.admin),
        params={"event_id": str(c.event_id), "order_id": order["id"], "category": "refund"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["total"] == 1 and response.json()["items"][0]["id"] == case["id"]
