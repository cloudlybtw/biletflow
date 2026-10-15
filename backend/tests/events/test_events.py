import asyncio
import io
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from PIL import Image
from sqlalchemy import func, select, update

from app.core.config import get_settings
from app.modules.events.models import Event, EventImage, EventStatus
from app.modules.history.models import AuditLog
from app.modules.ticketing.models import TicketType
from app.modules.users.models import StaffRole
from tests.factories import (
    auth_headers,
    create_event,
    create_organizer,
    create_staff_assignment,
    create_user,
    create_verified_user,
)


@pytest.fixture
async def owner(db_session):
    user = await create_verified_user(db_session)
    profile = await create_organizer(db_session, user)
    await db_session.commit()
    return user, profile


def payload(**overrides):
    start = datetime.now(UTC) + timedelta(days=30)
    return {
        "title": "Almaty Live",
        "starts_at": start.isoformat(),
        "ends_at": (start + timedelta(hours=3)).isoformat(),
        **overrides,
    }


async def new_event(client, owner, **overrides):
    response = await client.post(
        "/api/v1/events", json=payload(**overrides), headers=auth_headers(owner[0])
    )
    assert response.status_code == 201, response.text
    return response.json()


async def add_type(client, owner, event, **overrides):
    response = await client.post(
        f"/api/v1/events/{event['id']}/ticket-types",
        json={"name": "Standard", "quantity_total": 100, **overrides},
        headers=auth_headers(owner[0]),
    )
    assert response.status_code == 201, response.text
    return response.json()


async def test_seeded_catalog_and_venue_layout(client):
    categories = (await client.get("/api/v1/event-categories")).json()["items"]
    assert len(categories) == 4
    assert all(c["name_kk"] and c["name_ru"] and c["name_en"] for c in categories)
    page = (await client.get("/api/v1/event-categories?limit=1&offset=1")).json()
    assert page == {"items": categories[1:2], "total": 4}
    assert (await client.get("/api/v1/event-categories?limit=101")).status_code == 422
    venue = (await client.get("/api/v1/venues/20000000-0000-0000-0000-000000000001")).json()
    assert len(venue["price_categories"]) == 2
    assert len(venue["sections"][0]["rows"]) == 2
    assert sum(len(r["seats"]) for r in venue["sections"][0]["rows"]) == 20


async def test_ticket_type_and_staff_pages_preserve_visibility(client, db_session, owner):
    event = await new_event(client, owner)
    await add_type(client, owner, event)
    await add_type(client, owner, event, name="Hidden", is_hidden=True)
    await add_type(client, owner, event, name="Second visible")
    event_id = uuid.UUID(event["id"])
    staff = await create_verified_user(db_session)
    await create_staff_assignment(db_session, event_id, staff, StaffRole.EVENT_ADMIN)
    await create_staff_assignment(db_session, event_id, staff, StaffRole.SUPPORT_AGENT)
    await db_session.commit()
    path = f"/api/v1/events/{event_id}"
    assert (await client.post(path + "/publish", headers=auth_headers(owner[0]))).status_code == 200
    public = (await client.get(path + "/ticket-types")).json()
    assert public["total"] == 2 and all(not item["is_hidden"] for item in public["items"])
    page = (await client.get(path + "/ticket-types?limit=1&offset=1")).json()
    assert page == {"items": public["items"][1:2], "total": 2}
    private = (await client.get(path + "/ticket-types", headers=auth_headers(owner[0]))).json()
    assert private["total"] == 3
    staff_page = (
        await client.get(path + "/staff?limit=1&offset=1", headers=auth_headers(owner[0]))
    ).json()
    assert staff_page["total"] == 2 and len(staff_page["items"]) == 1
    assert (
        await client.get(path + "/staff?limit=1", headers=auth_headers(staff))
    ).status_code == 403


async def test_draft_edit_preview_publish_unpublish_cancel_audited(client, db_session, owner):
    event = await new_event(client, owner)
    url = f"/api/v1/events/{event['id']}"
    assert event["status"] == "draft"
    assert (await client.get(url, headers=auth_headers(owner[0]))).status_code == 200
    assert (await client.get(f"/api/v1/events/by-slug/{event['slug']}")).status_code == 404
    assert (await client.post(url + "/publish", headers=auth_headers(owner[0]))).json()["error"][
        "code"
    ] == "EVENT_HAS_NO_TICKETS"
    edit = await client.patch(
        url, json={"title": "Updated", "description": "Concert"}, headers=auth_headers(owner[0])
    )
    assert edit.json()["slug"] == event["slug"]
    await add_type(client, owner, event)
    for action, expected in [
        ("publish", "published"),
        ("unpublish", "unpublished"),
        ("publish", "published"),
        ("cancel", "cancelled"),
    ]:
        response = await client.post(url + f"/{action}", headers=auth_headers(owner[0]))
        assert response.status_code == 200, response.text
        assert response.json()["status"] == expected
    assert (await client.post(url + "/publish", headers=auth_headers(owner[0]))).status_code == 409
    actions = (
        await db_session.scalars(
            select(AuditLog.action_type).where(AuditLog.event_id == uuid.UUID(event["id"]))
        )
    ).all()
    assert {
        "event.created",
        "event.updated",
        "event.published",
        "event.unpublished",
        "event.cancelled",
        "ticket_type.created",
    } <= set(actions)


@pytest.mark.parametrize(
    "visibility,browsable,detail",
    [("public", True, 200), ("unlisted", False, 200), ("private", False, 404)],
)
async def test_public_visibility(client, owner, visibility, browsable, detail):
    event = await new_event(client, owner, visibility=visibility)
    await add_type(client, owner, event)
    await client.post(f"/api/v1/events/{event['id']}/publish", headers=auth_headers(owner[0]))
    assert bool((await client.get("/api/v1/events")).json()["total"]) is browsable
    assert (await client.get(f"/api/v1/events/by-slug/{event['slug']}")).status_code == detail
    types = await client.get(f"/api/v1/events/{event['id']}/ticket-types")
    assert types.status_code == (404 if visibility == "private" else 200)


async def test_filters_and_literal_search(client, owner):
    event = await new_event(
        client,
        owner,
        venue_id="20000000-0000-0000-0000-000000000001",
        category_id="10000000-0000-0000-0000-000000000001",
    )
    await add_type(client, owner, event)
    await client.post(f"/api/v1/events/{event['id']}/publish", headers=auth_headers(owner[0]))
    good = {
        "city": "almaty",
        "q": "live",
        "category_id": event["category_id"],
        "date_from": (datetime.now(UTC) + timedelta(days=29)).isoformat(),
        "date_to": (datetime.now(UTC) + timedelta(days=31)).isoformat(),
    }
    assert (await client.get("/api/v1/events", params=good)).json()["total"] == 1
    for query in [
        {"city": "Astana"},
        {"q": "%"},
        {"category_id": str(uuid.uuid4())},
        {"date_to": datetime.now(UTC).isoformat()},
    ]:
        assert (await client.get("/api/v1/events", params=query)).json()["total"] == 0
    assert (
        await client.get("/api/v1/events", params={"date_from": "2026-01-01T00:00:00"})
    ).status_code == 422


@pytest.mark.parametrize(
    "changes",
    [
        {"ends_at": "2000-01-01T00:00:00Z"},
        {"timezone": "Unknown/Zone"},
        {"starts_at": None},
        {"title": "  "},
        {"seating_mode": "assigned"},
        {"venue_id": str(uuid.uuid4())},
        {"paid_sales_status": "active"},
        {"status": "published"},
        {
            "registration_opens_at": "2027-01-02T00:00:00Z",
            "registration_closes_at": "2027-01-01T00:00:00Z",
        },
    ],
)
async def test_invalid_partial_updates_rejected(client, owner, changes):
    event = await new_event(client, owner)
    response = await client.patch(
        f"/api/v1/events/{event['id']}", json=changes, headers=auth_headers(owner[0])
    )
    assert response.status_code == 422, response.text


async def test_create_requires_verified_organizer(client, db_session):
    user = await create_user(db_session)
    await create_organizer(db_session, user)
    await db_session.commit()
    assert (await client.post("/api/v1/events", json=payload())).status_code == 401
    assert (
        await client.post("/api/v1/events", json=payload(), headers=auth_headers(user))
    ).status_code == 403
    verified = await create_verified_user(db_session)
    await db_session.commit()
    assert (
        await client.post("/api/v1/events", json=payload(), headers=auth_headers(verified))
    ).status_code == 404


async def test_staff_roles_assignments_and_revocation(client, db_session, owner):
    event = await new_event(client, owner)
    users = [await create_verified_user(db_session) for _ in range(4)]
    await db_session.commit()
    url = f"/api/v1/events/{event['id']}"
    assert (
        await client.patch(url, json={"title": "attack"}, headers=auth_headers(users[3]))
    ).status_code == 404
    for user, role in zip(users, ["co_organizer", "event_admin", "support_agent"], strict=False):
        assigned = await client.post(
            url + "/staff",
            json={"email": user.email.upper(), "role": role},
            headers=auth_headers(owner[0]),
        )
        assert assigned.status_code == 201
        assert (await client.get(url, headers=auth_headers(user))).status_code == 200
        changed = await client.patch(url, json={"title": role}, headers=auth_headers(user))
        assert changed.status_code == (200 if role == "co_organizer" else 403)
        assert (
            await client.post(
                url + "/staff", json={"email": user.email, "role": role}, headers=auth_headers(user)
            )
        ).status_code == 403
        assert (
            await client.post(
                url + "/staff",
                json={"email": user.email, "role": role},
                headers=auth_headers(owner[0]),
            )
        ).status_code == 409
        if role == "event_admin":
            assert (await client.get("/api/v1/events/assigned", headers=auth_headers(user))).json()[
                "total"
            ] == 1
        assert (
            await client.delete(
                url + f"/staff/{assigned.json()['id']}", headers=auth_headers(owner[0])
            )
        ).status_code == 204
        assert (await client.get(url, headers=auth_headers(user))).status_code == 404
        assert (await client.get("/api/v1/events/assigned", headers=auth_headers(user))).json()[
            "total"
        ] == 0


async def test_capacity_and_reserved_inventory_guards(client, db_session, owner):
    event = await new_event(client, owner, capacity=100)
    ticket = await add_type(client, owner, event, price_amount=2000)
    assert event["paid_sales_status"] == "disabled"
    url = f"/api/v1/events/{event['id']}"
    await db_session.execute(
        update(TicketType)
        .where(TicketType.id == uuid.UUID(ticket["id"]))
        .values(quantity_reserved=10, quantity_sold=20)
    )
    await db_session.commit()
    assert (
        await client.patch(
            url + f"/ticket-types/{ticket['id']}",
            json={"quantity_total": 29},
            headers=auth_headers(owner[0]),
        )
    ).json()["error"]["code"] == "QUANTITY_BELOW_COMMITTED"
    valid = await client.patch(
        url + f"/ticket-types/{ticket['id']}",
        json={"quantity_total": 30, "price_amount": 1500, "is_hidden": True},
        headers=auth_headers(owner[0]),
    )
    assert valid.status_code == 200, valid.text
    assert (
        await client.patch(url, json={"capacity": 20}, headers=auth_headers(owner[0]))
    ).status_code == 409
    assert (
        await client.post(
            url + "/ticket-types",
            json={"name": "Extra", "quantity_total": 71},
            headers=auth_headers(owner[0]),
        )
    ).status_code == 409
    assert (
        await client.patch(
            url + f"/ticket-types/{ticket['id']}",
            json={"max_per_order": 0},
            headers=auth_headers(owner[0]),
        )
    ).status_code == 422


async def test_concurrent_inventory_adds_do_not_exceed_capacity(client, owner):
    event = await new_event(client, owner, capacity=10)
    responses = await asyncio.gather(
        *[
            client.post(
                f"/api/v1/events/{event['id']}/ticket-types",
                json={"name": name, "quantity_total": 10},
                headers=auth_headers(owner[0]),
            )
            for name in ["A", "B"]
        ]
    )
    assert sorted(r.status_code for r in responses) == [201, 409]


async def test_duplicate_resets_inventory_and_private_fields(client, db_session, owner):
    event = await new_event(client, owner)
    ticket = await add_type(client, owner, event, price_amount=2500)
    await db_session.execute(
        update(TicketType)
        .where(TicketType.id == uuid.UUID(ticket["id"]))
        .values(quantity_reserved=5, quantity_sold=10)
    )
    await db_session.execute(
        update(Event)
        .where(Event.id == uuid.UUID(event["id"]))
        .values(status=EventStatus.PUBLISHED, paid_sales_status="active")
    )
    await db_session.commit()
    response = await client.post(
        f"/api/v1/events/{event['id']}/duplicate", headers=auth_headers(owner[0])
    )
    assert response.status_code == 201, response.text
    duplicate = response.json()
    assert duplicate["status"] == "draft" and duplicate["paid_sales_status"] == "disabled"
    assert duplicate["slug"] != event["slug"]
    types = (
        await client.get(
            f"/api/v1/events/{duplicate['id']}/ticket-types", headers=auth_headers(owner[0])
        )
    ).json()["items"]
    assert types[0]["quantity_sold"] == types[0]["quantity_reserved"] == 0
    assert types[0]["price_amount"] == 2500
    original = await db_session.get(Event, uuid.UUID(event["id"]))
    copy = await db_session.get(Event, uuid.UUID(duplicate["id"]))
    assert original.ics_uid != copy.ics_uid


@pytest.mark.parametrize("age,expected", [(30, "Upcoming"), (-1, "Completed")])
async def test_my_event_classification(client, db_session, owner, age, expected):
    start = datetime.now(UTC) + timedelta(days=age)
    await create_event(db_session, owner[1], starts_at=start, ends_at=start + timedelta(hours=1))
    await db_session.commit()
    mine = (await client.get("/api/v1/events/my", headers=auth_headers(owner[0]))).json()
    assert mine["items"][0]["classification"] == expected


async def test_delete_draft_retains_audit_and_hides_it(client, db_session, owner):
    event = await new_event(client, owner)
    url = f"/api/v1/events/{event['id']}"
    assert (await client.delete(url, headers=auth_headers(owner[0]))).status_code == 204
    assert (await client.get(url, headers=auth_headers(owner[0]))).status_code == 404
    assert (await client.get("/api/v1/events/my", headers=auth_headers(owner[0]))).json()[
        "total"
    ] == 0
    assert (
        await db_session.scalar(
            select(func.count())
            .select_from(AuditLog)
            .where(AuditLog.event_id == uuid.UUID(event["id"]))
        )
        == 2
    )


async def test_images_cover_safety_visibility_and_deletion(
    client, db_session, owner, tmp_path, monkeypatch
):
    monkeypatch.setattr(get_settings(), "media_root", tmp_path)
    event = await new_event(client, owner)
    url = f"/api/v1/events/{event['id']}/images"
    out = io.BytesIO()
    Image.new("RGB", (10, 10), "red").save(out, format="PNG")
    uploads = []
    for _ in range(2):
        response = await client.post(
            url,
            files={"file": ("../../evil.png", out.getvalue(), "image/png")},
            data={"is_cover": "true"},
            headers=auth_headers(owner[0]),
        )
        assert response.status_code == 201, response.text
        uploads.append(response.json())
    page = await client.get(url + "?limit=1&offset=1", headers=auth_headers(owner[0]))
    assert page.status_code == 200 and page.json()["total"] == 2
    assert len(page.json()["items"]) == 1
    assert (await client.get(url + "?limit=1&offset=1")).status_code == 404
    assert (
        await db_session.scalar(
            select(func.count()).select_from(EventImage).where(EventImage.is_cover)
        )
        == 1
    )
    assert (await client.get(uploads[0]["url"])).status_code == 404
    assert (await client.get(uploads[0]["url"], headers=auth_headers(owner[0]))).headers[
        "content-type"
    ] == "image/png"
    invalid = await client.post(
        url, files={"file": ("fake.png", b"<script/>", "image/png")}, headers=auth_headers(owner[0])
    )
    assert invalid.status_code == 422
    monkeypatch.setattr(get_settings(), "image_max_bytes", 4)
    assert (
        await client.post(
            url,
            files={"file": ("large.png", out.getvalue(), "image/png")},
            headers=auth_headers(owner[0]),
        )
    ).status_code == 413
    assert (
        await client.patch(
            url + f"/{uploads[0]['id']}", json={"is_cover": True}, headers=auth_headers(owner[0])
        )
    ).status_code == 200
    assert (
        await client.delete(url + f"/{uploads[0]['id']}", headers=auth_headers(owner[0]))
    ).status_code == 204
    assert not (tmp_path / f"{uploads[0]['id']}.png").exists()
