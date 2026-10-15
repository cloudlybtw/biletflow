import asyncio
import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import func, select, update

from app.modules.events.models import Event
from app.modules.history.models import AuditLog
from app.modules.notifications.models import Notification
from app.modules.orders.models import OrderItem
from app.modules.support import service
from app.modules.support.models import SupportCase, SupportMessage
from app.modules.users.models import StaffAssignment, User
from tests.factories import (
    auth_headers,
    create_event,
)
from tests.support.helpers import assign, open_case, opened_case, reply, set_status


@pytest.mark.parametrize("source", ["event", "order", "ticket"])
async def test_attendee_case_infers_purchase_context_and_records_initial_message(
    client, db_session, ctx, source
):
    order_id = await db_session.scalar(
        select(OrderItem.order_id).where(OrderItem.id == ctx.ticket.order_item_id)
    )
    context = (
        {"event_id": str(ctx.event_id)}
        if source == "event"
        else {
            "event_id": None,
            f"{source}_id": str(ctx.ticket.id if source == "ticket" else order_id),
        }
    )
    case = await opened_case(client, ctx, **context)
    assert case["case_number"].startswith("BFS-") and case["status"] == "open"
    assert case["opened_by_user_id"] == str(ctx.buyer.id) and case["event_id"] == str(ctx.event_id)
    assert case["order_id"] == (None if source == "event" else str(order_id))
    assert case["ticket_id"] == (str(ctx.ticket.id) if source == "ticket" else None)
    path = f"/api/v1/support/cases/{case['id']}"
    detail = await client.get(path, headers=auth_headers(ctx.buyer))
    assert detail.status_code == 200 and detail.json() == case
    thread = await client.get(path + "/messages", headers=auth_headers(ctx.buyer))
    assert thread.status_code == 200 and thread.json()["total"] == 1
    message = thread.json()["items"][0]
    assert message["body"] == "Please help." and message["sender_role"] == "requester"
    assert case["last_message_at"] == message["created_at"]
    notices = (await db_session.scalars(select(Notification))).all()
    assert {n.user_id for n in notices} == {ctx.owner.id, ctx.staff.id, ctx.co.id}
    assert all(n.channel == "in_app" and n.status == "sent" for n in notices)
    assert all("Please help" not in str(n.payload) for n in notices)
    assert (
        await db_session.scalar(
            select(func.count())
            .select_from(AuditLog)
            .where(AuditLog.action_type == "support.opened")
        )
        == 1
    )


async def test_organizer_platform_case_is_private_from_event_support_staff(client, db_session, ctx):
    case = await opened_case(client, ctx, user=ctx.owner, case_type="organizer", category="account")
    assert case["case_type"] == "organizer"
    for user in [ctx.staff, ctx.co, ctx.scanner, ctx.buyer]:
        assert (
            await client.get(f"/api/v1/support/cases/{case['id']}", headers=auth_headers(user))
        ).status_code == 404
    assert (await reply(client, case, ctx.admin)).status_code == 201
    assert (await set_status(client, case, ctx.admin, "in_progress")).status_code == 200
    assert (await assign(client, case, ctx.admin, ctx.admin)).status_code == 200
    invalid = await assign(client, case, ctx.admin, ctx.staff)
    assert (
        invalid.status_code == 400 and invalid.json()["error"]["code"] == "SUPPORT_ASSIGNEE_INVALID"
    )
    assert (await set_status(client, case, ctx.owner, "resolved")).status_code == 403
    assert (await reply(client, case, ctx.owner)).status_code == 201
    inbox = await client.get(
        f"/api/v1/events/{ctx.event_id}/support/cases", headers=auth_headers(ctx.staff)
    )
    assert inbox.status_code == 200 and inbox.json()["total"] == 0
    admin = await client.get(
        "/api/v1/admin/support/cases?case_type=organizer", headers=auth_headers(ctx.admin)
    )
    assert admin.status_code == 200 and admin.json()["total"] == 1


async def test_platform_case_without_event_and_organizer_validation(client, db_session, ctx):
    response = await open_case(client, ctx, user=ctx.owner, case_type="organizer", event_id=None)
    assert response.status_code == 201 and response.json()["event_id"] is None
    assert (await open_case(client, ctx, case_type="organizer", event_id=None)).status_code == 403
    other_event = await create_event(db_session)
    await db_session.commit()
    assert (
        await open_case(
            client, ctx, user=ctx.owner, case_type="organizer", event_id=str(other_event)
        )
    ).status_code == 404


@pytest.mark.parametrize("source", ["ticket", "order"])
async def test_foreign_purchase_context_is_hidden(client, db_session, ctx, source):
    order_id = await db_session.scalar(
        select(OrderItem.order_id).where(OrderItem.id == ctx.ticket.order_item_id)
    )
    changes = {
        "event_id": None,
        f"{source}_id": str(ctx.ticket.id if source == "ticket" else order_id),
    }
    assert (await open_case(client, ctx, user=ctx.other, **changes)).status_code == 404


async def test_mismatched_context_and_private_event_rejected(client, db_session, ctx):
    other_event = await create_event(db_session, ctx.profile)
    await db_session.commit()
    result = await open_case(client, ctx, ticket_id=str(ctx.ticket.id), event_id=str(other_event))
    assert result.status_code == 400 and result.json()["error"]["code"] == "SUPPORT_CONTEXT_INVALID"
    assert (
        await open_case(client, ctx, ticket_id=str(ctx.ticket.id), order_id=str(uuid.uuid4()))
    ).status_code == 400
    assert (await open_case(client, ctx, event_id=str(other_event))).status_code == 404
    assert (await open_case(client, ctx, event_id=str(uuid.uuid4()))).status_code == 404


@pytest.mark.parametrize("role", ["owner", "co", "staff"])
async def test_active_event_support_roles_can_read_reply_assign_and_change_status(
    client, ctx, role
):
    case = await opened_case(client, ctx)
    user = getattr(ctx, role)
    assert (
        await client.get(f"/api/v1/support/cases/{case['id']}", headers=auth_headers(user))
    ).status_code == 200
    assert (await reply(client, case, user)).status_code == 201
    assert (await assign(client, case, user, ctx.staff)).status_code == 200
    assert (await set_status(client, case, user, "waiting_for_customer")).status_code == 200
    inbox = await client.get(
        f"/api/v1/events/{ctx.event_id}/support/cases", headers=auth_headers(user)
    )
    assert inbox.status_code == 200 and inbox.json()["total"] == 1


@pytest.mark.parametrize("role", ["other", "scanner"])
@pytest.mark.parametrize(
    "method,suffix,data",
    [
        ("GET", "", None),
        ("GET", "/messages", None),
        ("POST", "/messages", {"body": "attack"}),
        ("PATCH", "/status", {"status": "resolved"}),
        ("PATCH", "/assignment", {"assigned_to_user_id": None}),
    ],
)
async def test_unrelated_or_checkin_only_users_cannot_access_cases(
    client, ctx, role, method, suffix, data
):
    case = await opened_case(client, ctx)
    result = await client.request(
        method,
        f"/api/v1/support/cases/{case['id']}" + suffix,
        json=data,
        headers=auth_headers(getattr(ctx, role)),
    )
    assert result.status_code == 404


async def test_platform_admin_has_read_only_moderation_of_attendee_cases(client, ctx):
    case = await opened_case(client, ctx)
    assert (
        await reply(client, case, ctx.staff, body="staff secret", is_internal_note=True)
    ).status_code == 201
    path = f"/api/v1/support/cases/{case['id']}"
    for suffix in ["", "/messages"]:
        result = await client.get(path + suffix, headers=auth_headers(ctx.admin))
        assert result.status_code == 200
    thread = await client.get(path + "/messages", headers=auth_headers(ctx.admin))
    assert any(m["is_internal_note"] for m in thread.json()["items"])
    assert (await reply(client, case, ctx.admin)).status_code == 403
    assert (await assign(client, case, ctx.admin, ctx.staff)).status_code == 403
    assert (await set_status(client, case, ctx.admin, "resolved")).status_code == 403


async def test_internal_notes_are_absent_from_requester_messages_totals_and_notifications(
    client, db_session, ctx
):
    case = await opened_case(client, ctx)
    before = await db_session.scalar(select(func.count()).select_from(Notification))
    internal = await reply(
        client, case, ctx.staff, body="INTERNAL PRIVATE NOTE", is_internal_note=True
    )
    assert internal.status_code == 201 and internal.json()["sender_role"] == "staff"
    after_note = await client.get(
        f"/api/v1/support/cases/{case['id']}", headers=auth_headers(ctx.buyer)
    )
    assert after_note.json()["last_message_at"] == case["last_message_at"]
    assert after_note.json()["updated_at"] == case["updated_at"]
    assert await db_session.scalar(select(func.count()).select_from(Notification)) == before
    requester = await client.get(
        f"/api/v1/support/cases/{case['id']}/messages", headers=auth_headers(ctx.buyer)
    )
    assert requester.json()["total"] == 1 and "INTERNAL PRIVATE NOTE" not in requester.text
    assert (await reply(client, case, ctx.buyer, is_internal_note=True)).status_code == 403
    assert (await reply(client, case, ctx.staff, body="PUBLIC REPLY")).status_code == 201
    notices = await client.get("/api/v1/notifications", headers=auth_headers(ctx.buyer))
    assert notices.status_code == 200 and notices.json()["total"] == 1
    assert "PRIVATE" not in notices.text and "PUBLIC REPLY" not in notices.text


async def test_polling_is_inclusive_aware_and_paginated(client, ctx):
    case = await opened_case(client, ctx)
    result = await reply(client, case, ctx.buyer)
    stamp = result.json()["created_at"]
    path = f"/api/v1/support/cases/{case['id']}/messages"
    response = await client.get(
        path, params={"since": stamp, "limit": 1}, headers=auth_headers(ctx.buyer)
    )
    assert response.status_code == 200 and response.json()["total"] == 1
    assert response.json()["items"][0]["id"] == result.json()["id"]
    assert (
        await client.get(
            path, params={"since": "2026-01-01T00:00:00"}, headers=auth_headers(ctx.buyer)
        )
    ).status_code == 422
    page = await client.get(path + "?limit=1&offset=1", headers=auth_headers(ctx.buyer))
    assert page.json()["total"] == 2 and len(page.json()["items"]) == 1


async def test_assignment_status_and_reopen_are_audited_and_idempotent(client, db_session, ctx):
    case = await opened_case(client, ctx)
    first = await assign(client, case, ctx.owner, ctx.staff)
    assert first.status_code == 200 and first.json()["assigned_to_user_id"] == str(ctx.staff.id)
    assert (await assign(client, case, ctx.owner, ctx.staff)).json()["updated_at"] == first.json()[
        "updated_at"
    ]
    assert (await assign(client, case, ctx.owner, None)).json()["assigned_to_user_id"] is None
    for status in ["in_progress", "waiting_for_customer", "resolved", "open"]:
        result = await set_status(client, case, ctx.staff, status)
        assert result.status_code == 200 and result.json()["status"] == status
        assert bool(result.json()["resolved_at"]) == (status == "resolved")
        repeated = await set_status(client, case, ctx.staff, status)
        assert repeated.json()["updated_at"] == result.json()["updated_at"]
    actions = (await db_session.scalars(select(AuditLog.action_type))).all()
    assert actions.count("support.assigned") == 2 and actions.count("support.status_changed") == 4
    assert (
        await db_session.scalar(
            select(func.count())
            .select_from(Notification)
            .where(
                Notification.user_id == ctx.buyer.id, Notification.type == "support_status_changed"
            )
        )
        == 4
    )
    assert (await set_status(client, case, ctx.buyer, "resolved")).status_code == 403
    assert (await assign(client, case, ctx.buyer, ctx.staff)).status_code == 403


@pytest.mark.parametrize("kind", ["unrelated", "scanner", "suspended", "revoked", "unknown"])
async def test_assignment_requires_an_active_authorized_assignee(client, db_session, ctx, kind):
    case = await opened_case(client, ctx)
    target = ctx.other if kind == "unrelated" else ctx.scanner if kind == "scanner" else ctx.staff
    if kind == "suspended":
        await db_session.execute(
            update(User).where(User.id == target.id).values(status="suspended")
        )
    if kind == "revoked":
        await db_session.execute(
            update(StaffAssignment)
            .where(StaffAssignment.id == ctx.assignment.id)
            .values(revoked_at=datetime.now(UTC))
        )
    await db_session.commit()
    if kind == "unknown":
        target = type("Missing", (), {"id": uuid.uuid4()})()
    result = await assign(client, case, ctx.owner, target)
    assert (
        result.status_code == 400 and result.json()["error"]["code"] == "SUPPORT_ASSIGNEE_INVALID"
    )


async def test_revocation_removes_access_and_stops_new_notifications(client, db_session, ctx):
    case = await opened_case(client, ctx)
    assert (await assign(client, case, ctx.owner, ctx.staff)).status_code == 200
    before = await db_session.scalar(
        select(func.count()).select_from(Notification).where(Notification.user_id == ctx.staff.id)
    )
    await db_session.execute(
        update(StaffAssignment)
        .where(StaffAssignment.id == ctx.assignment.id)
        .values(revoked_at=datetime.now(UTC))
    )
    await db_session.commit()
    assert (await reply(client, case, ctx.staff)).status_code == 404
    assert (
        await client.get(
            f"/api/v1/events/{ctx.event_id}/support/cases", headers=auth_headers(ctx.staff)
        )
    ).status_code == 404
    assert (await reply(client, case, ctx.buyer)).status_code == 201
    assert (
        await db_session.scalar(
            select(func.count())
            .select_from(Notification)
            .where(Notification.user_id == ctx.staff.id)
        )
        == before
    )


async def test_case_lists_are_scoped_and_filter_status_and_case_type(client, ctx):
    first = await opened_case(client, ctx)
    await opened_case(client, ctx)
    await opened_case(client, ctx, user=ctx.other)
    await opened_case(client, ctx, user=ctx.owner, case_type="organizer")
    await set_status(client, first, ctx.staff, "resolved")
    mine = await client.get(
        "/api/v1/support/cases?limit=1&offset=1", headers=auth_headers(ctx.buyer)
    )
    assert mine.status_code == 200 and mine.json()["total"] == 2 and len(mine.json()["items"]) == 1
    filtered = await client.get(
        "/api/v1/support/cases?status=resolved", headers=auth_headers(ctx.buyer)
    )
    assert filtered.json()["total"] == 1
    event = await client.get(
        f"/api/v1/events/{ctx.event_id}/support/cases?limit=1", headers=auth_headers(ctx.staff)
    )
    assert event.json()["total"] == 3 and len(event.json()["items"]) == 1
    admin = await client.get(
        "/api/v1/admin/support/cases?case_type=organizer", headers=auth_headers(ctx.admin)
    )
    assert admin.json()["total"] == 1
    assert (
        await client.get("/api/v1/admin/support/cases", headers=auth_headers(ctx.owner))
    ).status_code == 403
    assert (
        await client.get(
            f"/api/v1/events/{ctx.event_id}/support/cases", headers=auth_headers(ctx.scanner)
        )
    ).status_code == 403
    assert (
        await client.get(
            f"/api/v1/events/{ctx.event_id}/support/cases", headers=auth_headers(ctx.other)
        )
    ).status_code == 404


@pytest.mark.parametrize(
    "method,path,data",
    [
        ("POST", "/support/cases", {}),
        ("GET", "/support/cases", None),
        ("GET", "/admin/support/cases", None),
        ("GET", "/events/{event}/support/cases", None),
        ("GET", "/support/cases/{case}", None),
        ("GET", "/support/cases/{case}/messages", None),
        ("POST", "/support/cases/{case}/messages", {"body": "reply"}),
        ("PATCH", "/support/cases/{case}/assignment", {"assigned_to_user_id": None}),
        ("PATCH", "/support/cases/{case}/status", {"status": "open"}),
    ],
)
async def test_all_support_endpoints_require_auth(client, ctx, method, path, data):
    result = await client.request(
        method, "/api/v1" + path.format(event=ctx.event_id, case=uuid.uuid4()), json=data
    )
    assert result.status_code == 401


@pytest.mark.parametrize(
    "changes",
    [
        {"event_id": None},
        {"subject": " "},
        {"body": " "},
        {"category": "unknown"},
        {"opened_by_user_id": str(uuid.uuid4())},
        {"case_type": "organizer", "ticket_id": str(uuid.uuid4())},
    ],
)
async def test_case_schema_rejects_missing_context_blanks_and_forged_fields(client, ctx, changes):
    assert (await open_case(client, ctx, **changes)).status_code == 422


@pytest.mark.parametrize("action", ["create", "message", "status", "assignment"])
@pytest.mark.parametrize("failure", ["audit", "notification"])
async def test_support_changes_roll_back_if_audit_or_outbox_fails(
    client, db_session, ctx, monkeypatch, action, failure
):
    case = await opened_case(client, ctx)
    counts = {
        model: await db_session.scalar(select(func.count()).select_from(model))
        for model in [SupportCase, SupportMessage, Notification, AuditLog]
    }

    async def fail(*args, **kwargs):
        raise RuntimeError("persistence failure")

    monkeypatch.setattr(
        service.history if failure == "audit" else service.notifications,
        "record" if failure == "audit" else "enqueue",
        fail,
    )
    if action == "create":
        result = await open_case(client, ctx)
    elif action == "message":
        result = await reply(client, case, ctx.staff)
    elif action == "status":
        result = await set_status(client, case, ctx.staff, "resolved")
    else:
        result = await assign(client, case, ctx.owner, ctx.staff)
    assert result.status_code == 500
    for model, count in counts.items():
        assert await db_session.scalar(select(func.count()).select_from(model)) == count
    current = await db_session.get(SupportCase, uuid.UUID(case["id"]), populate_existing=True)
    assert current.status == "open" and current.assigned_to_user_id is None


async def test_concurrent_replies_have_committed_monotonic_timestamps(client, db_session, ctx):
    case = await opened_case(client, ctx)
    results = await asyncio.gather(reply(client, case, ctx.buyer), reply(client, case, ctx.staff))
    assert all(r.status_code == 201 for r in results), [r.text for r in results]
    stamps = sorted(r.json()["created_at"] for r in results)
    assert stamps[0] < stamps[1]
    current = await db_session.get(SupportCase, uuid.UUID(case["id"]), populate_existing=True)
    assert current.last_message_at == datetime.fromisoformat(stamps[1])
    assert await db_session.scalar(select(func.count()).select_from(SupportMessage)) == 3


@pytest.mark.parametrize("action", ["status", "assignment"])
async def test_duplicate_concurrent_staff_updates_emit_one_change(client, db_session, ctx, action):
    case = await opened_case(client, ctx)

    async def mutate():
        return (
            await set_status(client, case, ctx.owner, "in_progress")
            if action == "status"
            else await assign(client, case, ctx.owner, ctx.staff)
        )

    results = await asyncio.gather(mutate(), mutate(), mutate())
    assert all(r.status_code == 200 for r in results)
    assert (
        await db_session.scalar(
            select(func.count())
            .select_from(AuditLog)
            .where(
                AuditLog.action_type
                == ("support.status_changed" if action == "status" else "support.assigned")
            )
        )
        == 1
    )


async def test_concurrent_case_creation_generates_unique_case_numbers(client, ctx):
    cases = await asyncio.gather(*(open_case(client, ctx) for _ in range(5)))
    assert all(c.status_code == 201 for c in cases), [c.text for c in cases]
    assert len({c.json()["case_number"] for c in cases}) == 5


async def test_private_cancelled_event_purchase_context_still_available_to_buyer(
    client, db_session, ctx
):
    await db_session.execute(
        update(Event)
        .where(Event.id == ctx.event_id)
        .values(status="cancelled", visibility="private")
    )
    await db_session.commit()
    assert (
        await open_case(client, ctx, event_id=None, ticket_id=str(ctx.ticket.id))
    ).status_code == 201
    assert (await open_case(client, ctx)).status_code == 404


async def test_event_support_cannot_read_cases_for_another_event(client, db_session, ctx):
    from types import SimpleNamespace

    from app.modules.events.models import EventStatus

    other_event = await create_event(db_session, ctx.profile, status=EventStatus.PUBLISHED)
    await db_session.commit()
    other = SimpleNamespace(**{**vars(ctx), "event_id": other_event})
    case = await opened_case(client, other)
    assert (
        await client.get(f"/api/v1/support/cases/{case['id']}", headers=auth_headers(ctx.staff))
    ).status_code == 404
    assert (await reply(client, case, ctx.staff)).status_code == 404
    listing = await client.get(
        f"/api/v1/events/{ctx.event_id}/support/cases", headers=auth_headers(ctx.staff)
    )
    assert listing.json()["total"] == 0


async def test_deleted_draft_case_retains_requester_history_without_notifying_former_staff(
    client, db_session, ctx
):
    from types import SimpleNamespace

    from app.modules.users.models import StaffRole
    from tests.factories import create_staff_assignment

    event_id = await create_event(db_session, ctx.profile)
    await create_staff_assignment(db_session, event_id, ctx.staff, StaffRole.SUPPORT_AGENT)
    await create_staff_assignment(db_session, event_id, ctx.co, StaffRole.CO_ORGANIZER)
    await db_session.commit()
    other = SimpleNamespace(**{**vars(ctx), "event_id": event_id})
    case = await opened_case(client, other, user=ctx.staff)
    deleted = await client.delete(f"/api/v1/events/{event_id}", headers=auth_headers(ctx.owner))
    assert deleted.status_code == 204
    before = await db_session.scalar(select(func.count()).select_from(Notification))
    assert (await reply(client, case, ctx.staff)).status_code == 201
    assert await db_session.scalar(select(func.count()).select_from(Notification)) == before
    assert (
        await client.get(f"/api/v1/support/cases/{case['id']}", headers=auth_headers(ctx.co))
    ).status_code == 404
    assert (
        await client.get(f"/api/v1/support/cases/{case['id']}", headers=auth_headers(ctx.admin))
    ).status_code == 200
