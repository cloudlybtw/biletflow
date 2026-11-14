from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select, update

from app.modules.events.models import Event
from app.modules.history.models import AuditLog
from app.modules.notifications.models import Notification, NotificationType
from app.modules.operations.models import EventReport
from tests.factories import auth_headers, complete_purchase
from tests.support.helpers import opened_case


async def test_simulated_payout_lifecycle_permissions_idempotency_and_notifications(
    client, db_session, reporting_context
):
    c = reporting_context
    await complete_purchase(client, c)
    url = f"/api/v1/events/{c.event_id}/payouts"
    assert (await client.post(url, headers=auth_headers(c.buyer))).status_code == 404
    assert (await client.post(url, headers=auth_headers(c.owner))).status_code == 409
    await db_session.execute(
        update(Event)
        .where(Event.id == c.event_id)
        .values(
            starts_at=datetime.now(UTC) - timedelta(days=2),
            ends_at=datetime.now(UTC) - timedelta(days=1),
        )
    )
    await db_session.commit()
    response = await client.post(url, headers=auth_headers(c.owner))
    assert response.status_code == 200, response.text
    payout = response.json()
    assert payout["simulated"] is True and payout["amount"] == 1000
    assert (await client.post(url, headers=auth_headers(c.owner))).json()["id"] == payout["id"]
    path = f"/api/v1/admin/payouts/{payout['id']}"
    assert (
        await client.patch(
            path, json={"status": "paid", "note": "demo"}, headers=auth_headers(c.admin)
        )
    ).status_code == 409
    assert (
        await client.patch(
            path, json={"status": "processing", "note": "demo"}, headers=auth_headers(c.owner)
        )
    ).status_code == 403
    for status in ["processing", "failed", "processing", "paid"]:
        result = await client.patch(
            path, json={"status": status, "note": "Demo transition"}, headers=auth_headers(c.admin)
        )
        assert result.status_code == 200, result.text
        assert result.json()["status"] == status
    assert (
        await client.patch(
            path, json={"status": "failed", "note": "demo"}, headers=auth_headers(c.admin)
        )
    ).status_code == 409
    assert (
        await db_session.scalar(
            select(func.count())
            .select_from(Notification)
            .where(Notification.type == NotificationType.PAYOUT_STATUS)
        )
        == 10
    )
    assert (
        await db_session.scalar(
            select(func.count()).select_from(AuditLog).where(AuditLog.action_type.like("payout.%"))
        )
        == 5
    )


async def test_event_report_queue_is_private_and_review_is_audited(
    client, db_session, reporting_context
):
    c = reporting_context
    path = f"/api/v1/events/{c.event_id}/reports"
    data = {"reason": "Potentially misleading event information"}
    assert (await client.post(path, json=data)).status_code == 401
    result = await client.post(path, json=data, headers=auth_headers(c.buyer))
    assert result.status_code == 201, result.text
    report_id = result.json()["id"]
    assert (await client.post(path, json=data, headers=auth_headers(c.buyer))).json()[
        "id"
    ] == report_id
    assert await db_session.scalar(select(func.count()).select_from(EventReport)) == 1
    queue = "/api/v1/admin/event-reports"
    assert (await client.get(queue, headers=auth_headers(c.owner))).status_code == 403
    assert (await client.get(queue, headers=auth_headers(c.admin))).json()["total"] == 1
    for status in ["reviewing", "resolved"]:
        result = await client.patch(
            f"{queue}/{report_id}",
            json={"status": status, "resolution": "Reviewed by demo administrator"},
            headers=auth_headers(c.admin),
        )
        assert result.status_code == 200, result.text
    assert (
        await client.patch(
            f"{queue}/{report_id}",
            json={"status": "reviewing", "resolution": "again"},
            headers=auth_headers(c.admin),
        )
    ).status_code == 409


async def test_support_escalation_preserves_context_and_denies_requester(client, reporting_context):
    c = reporting_context
    case = await opened_case(client, c)
    path = f"/api/v1/support/cases/{case['id']}/escalate"
    message_path = f"/api/v1/support/cases/{case['id']}/messages"
    assert (
        await client.post(message_path, json={"body": "Admin reply"}, headers=auth_headers(c.admin))
    ).status_code == 403
    assert (
        await client.post(path, json={"reason": "Needs admin"}, headers=auth_headers(c.buyer))
    ).status_code == 403
    result = await client.post(
        path, json={"reason": "Needs platform moderation"}, headers=auth_headers(c.support)
    )
    assert result.status_code == 200, result.text
    assert result.json()["event_id"] == str(c.event_id) and result.json()["escalated_at"]
    repeat = await client.post(path, json={"reason": "duplicate"}, headers=auth_headers(c.support))
    assert repeat.json()["escalated_at"] == result.json()["escalated_at"]
    queue = await client.get(
        "/api/v1/admin/support/cases?escalated=true", headers=auth_headers(c.admin)
    )
    assert queue.json()["total"] == 1
    assert (
        await client.post(
            message_path, json={"body": "Escalated admin reply"}, headers=auth_headers(c.admin)
        )
    ).status_code == 201
    assigned = await client.patch(
        f"/api/v1/support/cases/{case['id']}/assignment",
        json={"assigned_to_user_id": str(c.admin.id)},
        headers=auth_headers(c.admin),
    )
    assert assigned.status_code == 200, assigned.text


async def test_inventory_counts_authoritative_tickets_and_permissions(client, reporting_context):
    c = reporting_context
    await complete_purchase(client, c)
    path = f"/api/v1/events/{c.event_id}/inventory"
    assert (await client.get(path, headers=auth_headers(c.buyer))).status_code == 404
    result = await client.get(path, headers=auth_headers(c.co))
    assert result.status_code == 200, result.text
    row = result.json()["items"][0]
    assert (
        row["sold"] == 1
        and row["available"] == row["capacity"] - 1
        and row["refunded"] == row["checked_in"] == 0
    )
