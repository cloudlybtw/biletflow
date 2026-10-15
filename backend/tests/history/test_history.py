from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select, update

from app.modules.events.models import Event
from app.modules.history.models import AuditLog
from app.modules.users.models import StaffAssignment
from tests.factories import auth_headers, complete_purchase, create_event, create_issued_ticket

PATHS = ["history", "orders", "tickets", "refunds", "checkin/records"]


@pytest.mark.parametrize("path", PATHS)
async def test_event_record_lists_permissions_and_pagination(client, reporting_context, path):
    c = reporting_context
    await complete_purchase(client, c)
    url = f"/api/v1/events/{c.event_id}/{path}"
    for user in [c.owner, c.co, c.admin]:
        response = await client.get(url, headers=auth_headers(user), params={"limit": 1})
        assert response.status_code == 200, response.text
        assert "total" in response.json() and len(response.json()["items"]) <= 1
    for user, expected in [
        (c.buyer, 404),
        (c.support, 403),
        (c.event_admin, 200 if path == "checkin/records" else 403),
    ]:
        assert (await client.get(url, headers=auth_headers(user))).status_code == expected
    assert (await client.get(url)).status_code == 401


async def test_retained_details_scoped_and_token_private_after_cancellation(
    client, reporting_context, db_session
):
    c = reporting_context
    order = await complete_purchase(client, c)
    await client.post(f"/api/v1/events/{c.event_id}/cancel", headers=auth_headers(c.owner))
    for path, rid in [("orders", order["id"]), ("tickets", order["ticket_ids"][0])]:
        url = f"/api/v1/events/{c.event_id}/{path}/{rid}"
        for user in [c.owner, c.co, c.admin]:
            response = await client.get(url, headers=auth_headers(user))
            assert response.status_code == 200, response.text
            assert "qr_token" not in response.text and "provider_payload" not in response.text
        assert (await client.get(url, headers=auth_headers(c.buyer))).status_code == 404
        assert (await client.get(url, headers=auth_headers(c.event_admin))).status_code == 403
        assert (await client.get(url)).status_code == 401
    foreign = await create_event(db_session, c.profile)
    ticket = await create_issued_ticket(db_session, foreign, c.buyer)
    await db_session.commit()
    assert (
        await client.get(
            f"/api/v1/events/{c.event_id}/tickets/{ticket.id}", headers=auth_headers(c.owner)
        )
    ).status_code == 404
    assert (
        await client.get(
            f"/api/v1/events/{foreign}/orders/{order['id']}", headers=auth_headers(c.owner)
        )
    ).status_code == 404
    for path in PATHS:
        response = await client.get(
            f"/api/v1/events/{c.event_id}/{path}", headers=auth_headers(c.co)
        )
        assert response.status_code == 200
    await db_session.execute(
        update(StaffAssignment)
        .where(StaffAssignment.id == c.assignment.id)
        .values(revoked_at=datetime.now(UTC))
    )
    await db_session.commit()
    assert (
        await client.get(f"/api/v1/events/{c.event_id}/history", headers=auth_headers(c.co))
    ).status_code == 404


async def test_real_actions_appear_in_chronological_timeline_without_private_metadata(
    client, reporting_context, db_session
):
    c = reporting_context
    headers = auth_headers(c.owner)
    event = f"/api/v1/events/{c.event_id}"
    await client.post(event + "/unpublish", headers=headers)
    await client.patch(event, headers=headers, json={"title": "History Event"})
    await client.patch(
        event + f"/ticket-types/{c.ticket_type.id}",
        headers=headers,
        json={"price_amount": 1100, "quantity_total": 110},
    )
    await client.post(event + "/publish", headers=headers)
    campaign = await client.post(
        event + "/campaigns",
        headers=headers,
        json={"name": "History Promo", "discount_type": "percent", "discount_value": 10},
    )
    assert campaign.status_code == 201, campaign.text
    cid = campaign.json()["id"]
    await client.post(event + f"/campaigns/{cid}/activate", headers=headers)
    order = await complete_purchase(client, c)
    case = await client.post(
        "/api/v1/support/cases",
        headers=auth_headers(c.buyer),
        json={
            "case_type": "attendee",
            "category": "refund",
            "subject": "Question",
            "order_id": order["id"],
            "body": "Private buyer text",
        },
    )
    assert case.status_code == 201, case.text
    await client.post(
        f"/api/v1/support/cases/{case.json()['id']}/messages",
        headers=headers,
        json={"body": "SECRET INTERNAL NOTE", "is_internal_note": True},
    )
    await client.patch(
        f"/api/v1/support/cases/{case.json()['id']}/status",
        headers=headers,
        json={"status": "in_progress"},
    )
    scan = await client.post(
        f"/api/v1/checkin/scan?event_id={c.event_id}",
        headers=auth_headers(c.event_admin),
        json={"ticket_id": order["ticket_ids"][0]},
    )
    await client.post(
        event + f"/checkin/records/{scan.json()['record_id']}/reverse", headers=headers, json={}
    )
    await client.post(
        event + f"/orders/{order['id']}/refunds",
        headers=headers,
        json={"reason": "Private refund reason"},
    )
    await client.post(event + f"/campaigns/{cid}/disable", headers=headers)
    await client.post(event + "/cancel", headers=headers)
    response = await client.get(event + "/history", headers=headers, params={"limit": 100})
    assert response.status_code == 200, response.text
    records = response.json()["items"]
    stored = list(
        (
            await db_session.scalars(
                select(AuditLog)
                .where(AuditLog.event_id == c.event_id)
                .order_by(AuditLog.occurred_at, AuditLog.id)
            )
        ).all()
    )
    assert [r["id"] for r in records] == [r.id for r in stored]
    assert {
        "event.published",
        "event.cancelled",
        "ticket_type.updated",
        "campaign.created",
        "promo_code.created",
        "campaign.disabled",
        "support.status_changed",
        "ticket.checked_in",
        "ticket.check_in_reversed",
        "refund.completed",
    } <= {r["action_type"] for r in records}
    price_change = next(r for r in records if r["action_type"] == "ticket_type.updated")
    assert "1000 -> 1100" in price_change["summary"] and "100 -> 110" in price_change["summary"]
    assert (
        "metadata" not in response.text
        and "SECRET" not in response.text
        and "Private refund reason" not in response.text
    )
    filtered = await client.get(
        event + "/history", headers=headers, params={"action_type": "refund.completed"}
    )
    assert filtered.json()["total"] == 1
    after = await client.get(
        event + "/history",
        headers=headers,
        params={"date_from": (datetime.now(UTC) + timedelta(days=1)).isoformat()},
    )
    assert after.json()["total"] == 0
    assert (
        await client.patch(event + f"/history/{records[0]['id']}", headers=headers, json={})
    ).status_code == 404


async def test_completed_event_classification_duplicate_excludes_history(
    client, reporting_context, db_session
):
    c = reporting_context
    await complete_purchase(client, c)
    await db_session.execute(
        update(Event)
        .where(Event.id == c.event_id)
        .values(
            starts_at=datetime.now(UTC) - timedelta(days=2),
            ends_at=datetime.now(UTC) - timedelta(days=1),
        )
    )
    await db_session.commit()
    event = f"/api/v1/events/{c.event_id}"
    response = await client.get(event, headers=auth_headers(c.owner))
    assert response.json()["classification"] == "Completed"
    duplicated = await client.post(event + "/duplicate", headers=auth_headers(c.owner))
    assert duplicated.status_code == 201, duplicated.text
    fresh = duplicated.json()["id"]
    for path in ["orders", "tickets", "refunds", "checkin/records", "support/cases", "campaigns"]:
        response = await client.get(f"/api/v1/events/{fresh}/{path}", headers=auth_headers(c.owner))
        assert response.status_code == 200, response.text
        assert response.json()["total"] == 0
    summary = await client.get(
        f"/api/v1/events/{fresh}/analytics/summary", headers=auth_headers(c.owner)
    )
    assert summary.json()["sold"] == summary.json()["gross_amount"] == 0
