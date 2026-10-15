import asyncio
import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import func, select, update

from app.modules.campaigns.models import Campaign, CampaignQR, PromoCode
from app.modules.checkin.models import CheckInRecord
from app.modules.history.models import AuditLog
from app.modules.tickets.models import Ticket
from app.modules.users.models import PlatformRole, StaffAssignment, StaffRole
from tests.factories import (
    auth_headers,
    create_event,
    create_issued_ticket,
    create_staff_assignment,
    create_verified_user,
)


async def scan(client, admission, *, user=None, event_id=None, **data):
    return await client.post(
        "/api/v1/checkin/scan",
        params={"event_id": str(event_id or admission.event_id)},
        json=data or {"token": admission.ticket.qr_token},
        headers=auth_headers(user or admission.staff),
    )


async def reverse(client, admission, record_id, *, user=None, event_id=None):
    return await client.post(
        f"/api/v1/events/{event_id or admission.event_id}/checkin/records/{record_id}/reverse",
        json={"device_id": "door-1", "notes": "Accidental admission"},
        headers=auth_headers(user or admission.staff),
    )


async def test_scan_returns_details_and_records_every_attempt(client, db_session, admission):
    response = await scan(client, admission, device_id="door-1", token=admission.ticket.qr_token)
    assert response.status_code == 201, response.text
    data = response.json()
    assert data["result"] == "valid" and data["source"] == "qr_scan"
    assert data["ticket"]["attendee_name"] == admission.buyer.full_name
    assert data["ticket"]["ticket_type_name"]
    assert data["ticket"]["status"] == "checked_in"
    assert data["ticket"]["check_in_record_id"] == data["record_id"]
    assert datetime.fromisoformat(data["scanned_at"]).utcoffset().total_seconds() == 0
    duplicate = await scan(client, admission)
    assert duplicate.json()["result"] == "duplicate"
    assert duplicate.json()["ticket"]["check_in_record_id"] == data["record_id"]
    records = (
        await db_session.scalars(select(CheckInRecord).order_by(CheckInRecord.scanned_at))
    ).all()
    assert len(records) == 2
    assert records[0].scanned_token == admission.ticket.qr_token
    assert records[0].device_id == "door-1"
    assert all(r.scanned_by_user_id == admission.staff.id for r in records)
    assert (
        await db_session.scalar(
            select(func.count())
            .select_from(AuditLog)
            .where(
                AuditLog.action_type == "ticket.checked_in", AuditLog.event_id == admission.event_id
            )
        )
        == 1
    )


@pytest.mark.parametrize("manual", [False, True])
async def test_one_admission_per_ticket_under_concurrent_scans(
    client, db_session, admission, manual
):
    data = (
        {"ticket_id": str(admission.ticket.id)} if manual else {"token": admission.ticket.qr_token}
    )
    # ASGI dependency supplies a distinct AsyncSession to each request.
    responses = await asyncio.gather(*(scan(client, admission, **data) for _ in range(8)))
    assert all(r.status_code == 201 for r in responses), [r.text for r in responses]
    assert sorted(r.json()["result"] for r in responses) == ["duplicate"] * 7 + ["valid"]
    assert await db_session.scalar(select(func.count()).select_from(CheckInRecord)) == 8
    assert (
        await db_session.scalar(
            select(func.count())
            .select_from(AuditLog)
            .where(AuditLog.action_type == "ticket.checked_in")
        )
        == 1
    )


@pytest.mark.parametrize(
    "token",
    [
        "bfc_unknown",
        "https://example.com/e/event?c=bfc_token",
        "http://example.com",
        "//example.com/e/event",
        "HTTPS://example.com",
        "https://[malformed",
    ],
)
async def test_campaign_qr_and_urls_never_grant_admission(client, db_session, admission, token):
    response = await scan(client, admission, token=token)
    assert response.status_code == 201
    assert response.json()["result"] == "campaign_code_rejected"
    assert response.json()["ticket"] is None
    record = await db_session.get(CheckInRecord, uuid.UUID(response.json()["record_id"]))
    assert record.ticket_id is None and record.scanned_token == token
    assert (
        await db_session.get(Ticket, admission.ticket.id, populate_existing=True)
    ).status == "valid"


async def test_legacy_campaign_token_rejected_even_when_it_matches_a_ticket(
    client, db_session, admission
):
    campaign = Campaign(
        event_id=admission.event_id, name="Legacy", discount_type="percent", discount_value=10
    )
    db_session.add(campaign)
    await db_session.flush()
    code = PromoCode(campaign_id=campaign.id, code="LEGACY")
    db_session.add(code)
    await db_session.flush()
    token = admission.ticket.qr_token
    db_session.add(
        CampaignQR(
            campaign_id=campaign.id,
            promo_code_id=code.id,
            token=token,
            target_url="https://example.com",
        )
    )
    await db_session.commit()
    response = await scan(client, admission)
    assert response.json()["result"] == "campaign_code_rejected"
    assert (
        await db_session.get(Ticket, admission.ticket.id, populate_existing=True)
    ).status == "valid"


@pytest.mark.parametrize("manual", [False, True])
async def test_wrong_event_logs_without_disclosing_or_changing_ticket(
    client, db_session, admission, manual
):
    foreign_event = await create_event(db_session, admission.profile)
    foreign = await create_issued_ticket(db_session, foreign_event, admission.buyer)
    await db_session.commit()
    data = {"ticket_id": str(foreign.id)} if manual else {"token": foreign.qr_token}
    response = await scan(client, admission, **data)
    assert response.json()["result"] == "wrong_event" and response.json()["ticket"] is None
    record = await db_session.get(CheckInRecord, uuid.UUID(response.json()["record_id"]))
    assert record.ticket_id == foreign.id and record.event_id == admission.event_id
    assert (await db_session.get(Ticket, foreign.id, populate_existing=True)).status == "valid"


@pytest.mark.parametrize("status", ["cancelled", "refunded"])
@pytest.mark.parametrize("manual", [False, True])
async def test_cancelled_or_refunded_ticket_cannot_enter(
    client, db_session, admission, status, manual
):
    await db_session.execute(
        update(Ticket)
        .where(Ticket.id == admission.ticket.id)
        .values(status=status, invalidated_at=datetime.now(UTC))
    )
    await db_session.commit()
    data = (
        {"ticket_id": str(admission.ticket.id)} if manual else {"token": admission.ticket.qr_token}
    )
    response = await scan(client, admission, **data)
    assert response.json()["result"] == status
    assert response.json()["ticket"]["checked_in_at"] is None
    assert await db_session.scalar(select(func.count()).select_from(CheckInRecord)) == 1


@pytest.mark.parametrize(
    "data", [{"token": "not-a-ticket"}, {"token": "   "}, {"ticket_id": str(uuid.uuid4())}]
)
async def test_unknown_ticket_logs_invalid(client, db_session, admission, data):
    response = await scan(client, admission, **data)
    assert response.status_code == 201 and response.json()["result"] == "invalid"
    assert response.json()["ticket"] is None
    assert await db_session.scalar(select(func.count()).select_from(CheckInRecord)) == 1


@pytest.mark.parametrize(
    "data",
    [
        {},
        {"token": ""},
        {"token": "x", "ticket_id": str(uuid.uuid4())},
        {"token": "x", "source": "manual_search"},
        {"token": "x" * 4097},
        {"ticket_id": "not-a-uuid"},
    ],
)
async def test_scan_schema_validation_never_changes_admission(client, db_session, admission, data):
    response = await client.post(
        "/api/v1/checkin/scan",
        params={"event_id": str(admission.event_id)},
        json=data,
        headers=auth_headers(admission.staff),
    )
    assert response.status_code == 422, response.text
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
    assert await db_session.scalar(select(func.count()).select_from(CheckInRecord)) == 0


@pytest.mark.parametrize("role", ["owner", "co_organizer", "event_admin"])
async def test_authorized_roles_can_admit_and_reverse(client, db_session, admission, role):
    if role == "owner":
        user = admission.owner
    elif role == "event_admin":
        user = admission.staff
    else:
        user = await create_verified_user(db_session)
        await create_staff_assignment(db_session, admission.event_id, user, StaffRole.CO_ORGANIZER)
        await db_session.commit()
    response = await scan(client, admission, user=user)
    assert response.status_code == 201
    undo = await reverse(client, admission, response.json()["record_id"], user=user)
    assert undo.status_code == 201 and undo.json()["ticket"]["status"] == "valid"


@pytest.mark.parametrize(
    "actor,expected",
    [
        ("anonymous", 401),
        ("buyer", 404),
        ("support", 403),
        ("platform_admin", 403),
        ("revoked", 404),
        ("other_event_admin", 404),
    ],
)
async def test_every_checkin_endpoint_enforces_event_permissions(
    client, db_session, admission, actor, expected
):
    success = await scan(client, admission)
    if actor == "anonymous":
        headers = {}
    elif actor == "buyer":
        headers = auth_headers(admission.buyer)
    else:
        user = await create_verified_user(
            db_session,
            **({"platform_role": PlatformRole.PLATFORM_ADMIN} if actor == "platform_admin" else {}),
        )
        if actor in ("support", "revoked", "other_event_admin"):
            event_id = (
                await create_event(db_session)
                if actor == "other_event_admin"
                else admission.event_id
            )
            await create_staff_assignment(
                db_session,
                event_id,
                user,
                StaffRole.SUPPORT_AGENT if actor == "support" else StaffRole.EVENT_ADMIN,
                revoked_at=datetime.now(UTC) if actor == "revoked" else None,
            )
        await db_session.commit()
        headers = auth_headers(user)
    prefix = f"/api/v1/events/{admission.event_id}/checkin"
    requests = [
        await client.post(
            "/api/v1/checkin/scan",
            params={"event_id": str(admission.event_id)},
            json={"token": admission.ticket.qr_token},
            headers=headers,
        ),
        await client.get(f"{prefix}/attendees", headers=headers),
        await client.get(f"{prefix}/counters", headers=headers),
        await client.post(
            f"{prefix}/records/{success.json()['record_id']}/reverse", json={}, headers=headers
        ),
    ]
    statuses = [403, 200, 200, 403] if actor == "platform_admin" else [expected] * 4
    assert [r.status_code for r in requests] == statuses, [r.text for r in requests]
    assert await db_session.scalar(select(func.count()).select_from(CheckInRecord)) == 1


async def test_revoked_assignment_stops_access_immediately(client, db_session, admission):
    await db_session.execute(
        update(StaffAssignment)
        .where(StaffAssignment.id == admission.assignment.id)
        .values(revoked_at=datetime.now(UTC))
    )
    await db_session.commit()
    assert (await scan(client, admission)).status_code == 404


async def test_manual_search_is_scoped_paginated_and_undoable(client, db_session, admission):
    second = await create_issued_ticket(
        db_session,
        admission.event_id,
        admission.buyer,
        attendee_name="Other attendee",
        attendee_email="other@example.com",
    )
    foreign_event = await create_event(db_session, admission.profile)
    await create_issued_ticket(db_session, foreign_event, admission.buyer)
    await db_session.commit()
    path = f"/api/v1/events/{admission.event_id}/checkin/attendees"
    headers = auth_headers(admission.staff)
    for term in ["Әлия", admission.buyer.email.upper(), admission.ticket.ticket_code.lower()]:
        response = await client.get(path, params={"q": term}, headers=headers)
        assert response.status_code == 200, response.text
        assert response.json()["total"] == 1
        assert response.json()["items"][0]["ticket_id"] == str(admission.ticket.id)
        assert "qr_token" not in response.json()["items"][0]
    listing = await client.get(path, params={"limit": 1, "offset": 1}, headers=headers)
    assert listing.json()["total"] == 2 and len(listing.json()["items"]) == 1
    for term in ["%", "_", "\\", "no-match"]:
        assert (await client.get(path, params={"q": term}, headers=headers)).json()["total"] == 0
    response = await scan(client, admission, ticket_id=str(second.id))
    assert response.json()["result"] == "valid" and response.json()["source"] == "manual_search"
    record_id = response.json()["record_id"]
    listing = (await client.get(path, params={"q": "other@example.com"}, headers=headers)).json()
    assert listing["items"][0]["check_in_record_id"] == record_id
    undone = await reverse(client, admission, record_id)
    assert undone.json()["source"] == "manual_search"
    assert undone.json()["reverses_record_id"] == record_id
    assert undone.json()["ticket"]["checked_in_at"] is None
    assert undone.json()["ticket"]["check_in_record_id"] is None
    original = await db_session.get(CheckInRecord, uuid.UUID(record_id))
    assert (
        original.action == "check_in"
        and original.result == "valid"
        and original.scanned_token is None
    )


async def test_reverse_is_audited_and_old_record_cannot_undo_new_admission(
    client, db_session, admission
):
    first = (await scan(client, admission)).json()
    undo = await reverse(client, admission, first["record_id"])
    assert undo.status_code == 201, undo.text
    assert undo.json()["action"] == "reverse" and undo.json()["ticket"]["status"] == "valid"
    second = (await scan(client, admission)).json()
    assert second["result"] == "valid"
    stale = await reverse(client, admission, first["record_id"])
    assert stale.status_code == 409 and stale.json()["error"]["code"] == "CHECKIN_NOT_REVERSIBLE"
    assert (
        await db_session.get(Ticket, admission.ticket.id, populate_existing=True)
    ).status == "checked_in"
    assert (await reverse(client, admission, undo.json()["record_id"])).status_code == 409
    assert (await reverse(client, admission, uuid.uuid4())).status_code == 404
    assert (
        await db_session.scalar(
            select(func.count())
            .select_from(AuditLog)
            .where(AuditLog.action_type == "ticket.check_in_reversed")
        )
        == 1
    )


async def test_duplicate_record_cannot_be_reversed(client, admission):
    await scan(client, admission)
    duplicate = (await scan(client, admission)).json()
    assert (await reverse(client, admission, duplicate["record_id"])).status_code == 409


@pytest.mark.parametrize("status", ["cancelled", "refunded"])
async def test_reverse_cannot_revalidate_invalidated_ticket(client, db_session, admission, status):
    original = (await scan(client, admission)).json()
    await db_session.execute(
        update(Ticket).where(Ticket.id == admission.ticket.id).values(status=status)
    )
    await db_session.commit()
    assert (await reverse(client, admission, original["record_id"])).status_code == 409
    assert (
        await db_session.get(Ticket, admission.ticket.id, populate_existing=True)
    ).status == status


async def test_reverse_record_from_another_event_is_hidden(client, db_session, admission):
    original = (await scan(client, admission)).json()
    other = await create_event(db_session, admission.profile)
    await db_session.commit()
    assert (
        await reverse(
            client, admission, original["record_id"], user=admission.owner, event_id=other
        )
    ).status_code == 404


async def test_concurrent_reversals_have_exactly_one_winner(client, db_session, admission):
    original = (await scan(client, admission)).json()
    responses = await asyncio.gather(
        *(reverse(client, admission, original["record_id"]) for _ in range(4))
    )
    assert sorted(r.status_code for r in responses) == [201, 409, 409, 409], [
        r.text for r in responses
    ]
    assert (
        await db_session.scalar(
            select(func.count())
            .select_from(CheckInRecord)
            .where(CheckInRecord.reverses_record_id == uuid.UUID(original["record_id"]))
        )
        == 1
    )


async def test_scan_and_reverse_race_preserves_consistent_admission(client, db_session, admission):
    original = (await scan(client, admission)).json()
    undo, scanned = await asyncio.gather(
        reverse(client, admission, original["record_id"]), scan(client, admission)
    )
    assert undo.status_code == scanned.status_code == 201, [undo.text, scanned.text]
    ticket = await db_session.get(Ticket, admission.ticket.id, populate_existing=True)
    if scanned.json()["result"] == "valid":
        assert ticket.status == "checked_in" and ticket.checked_in_at is not None
    else:
        assert scanned.json()["result"] == "duplicate" and ticket.status == "valid"
        assert ticket.checked_in_at is None


async def test_counters_count_active_registrations_and_follow_reversal(
    client, db_session, admission
):
    for status in ["valid", "cancelled", "refunded"]:
        await create_issued_ticket(db_session, admission.event_id, admission.buyer, status=status)
    other = await create_event(db_session, admission.profile)
    await create_issued_ticket(db_session, other, admission.buyer)
    await db_session.commit()
    path = f"/api/v1/events/{admission.event_id}/checkin/counters"
    headers = auth_headers(admission.staff)
    assert (await client.get(path, headers=headers)).json() == {"registered": 2, "checked_in": 0}
    original = (await scan(client, admission)).json()
    assert (await client.get(path, headers=headers)).json() == {"registered": 2, "checked_in": 1}
    await reverse(client, admission, original["record_id"])
    assert (await client.get(path, headers=headers)).json() == {"registered": 2, "checked_in": 0}


@pytest.mark.parametrize("operation", ["scan", "reverse"])
async def test_admission_and_reversal_roll_back_if_audit_write_fails(
    client, db_session, admission, monkeypatch, operation
):
    from app.modules.checkin import service

    original = (await scan(client, admission)).json() if operation == "reverse" else None

    async def failed_audit(*args, **kwargs):
        raise RuntimeError("Audit storage unavailable")

    monkeypatch.setattr(service, "audit_record", failed_audit)
    response = (
        (await reverse(client, admission, original["record_id"]))
        if original
        else (await scan(client, admission))
    )
    assert response.status_code == 500
    ticket = await db_session.get(Ticket, admission.ticket.id, populate_existing=True)
    assert ticket.status == ("checked_in" if original else "valid")
    assert await db_session.scalar(select(func.count()).select_from(CheckInRecord)) == (
        1 if original else 0
    )


async def test_checkout_pdf_and_digital_ticket_share_one_admission(client, db_session, admission):
    order_response = await client.post(
        f"/api/v1/events/{admission.event_id}/orders",
        json={"items": [{"ticket_type_id": str(admission.ticket.ticket_type_id), "quantity": 1}]},
        headers=auth_headers(admission.buyer),
    )
    assert order_response.status_code == 201, order_response.text
    order = order_response.json()
    assert order["status"] == "completed"
    ticket_id = order["ticket_ids"][0]
    ticket = (
        await client.get(f"/api/v1/tickets/{ticket_id}", headers=auth_headers(admission.buyer))
    ).json()
    assert (
        await client.get(ticket["pdf_url"], headers=auth_headers(admission.buyer))
    ).status_code == 200
    assert await db_session.scalar(select(func.count()).select_from(Ticket)) == 2
    admission_response = await scan(client, admission, token=ticket["qr_token"])
    assert admission_response.json()["result"] == "valid"
    duplicate = await scan(client, admission, ticket_id=ticket_id)
    assert duplicate.json()["result"] == "duplicate"
