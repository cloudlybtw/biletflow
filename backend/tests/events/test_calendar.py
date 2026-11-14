from sqlalchemy import select

from app.modules.events.calendar import escape, fold
from app.modules.events.models import Event
from tests.factories import auth_headers, create_event, create_organizer, create_verified_user


def test_calendar_escape_and_utf8_folding_block_injection():
    assert escape("Hi\r\nATTENDEE:bad,;\\") == "Hi\\nATTENDEE:bad\\,\\;\\\\"
    line = "SUMMARY:" + "Қазақша 🎵" * 30
    result = fold(line)
    assert all(len(part.encode()) <= 75 for part in result.split("\r\n"))
    assert result.replace("\r\n ", "") == line


async def test_calendar_uid_sequence_cancellation_and_private_access(client, db_session):
    owner = await create_verified_user(db_session)
    profile = await create_organizer(db_session, owner)
    event_id = await create_event(db_session, profile, status="published", title="Calendar demo")
    private_id = await create_event(db_session, profile, status="published", visibility="private")
    await db_session.commit()
    path = f"/api/v1/events/{event_id}"
    first = await client.get(path + "/calendar.ics")
    assert first.status_code == 200
    event = await db_session.scalar(select(Event).where(Event.id == event_id))
    assert f"UID:{event.ics_uid}" in first.text
    assert "STATUS:CONFIRMED" in first.text
    assert "SEQUENCE:0" in first.text
    assert (await client.get(f"/api/v1/events/{private_id}/calendar.ics")).status_code == 404
    assert (
        await client.get(f"/api/v1/events/{private_id}/calendar.ics", headers=auth_headers(owner))
    ).status_code == 200
    links = await client.get(path + "/calendar-links")
    assert links.json()["google"].startswith("https://calendar.google.com/")
    assert (await client.post(path + "/cancel", headers=auth_headers(owner))).status_code == 200
    cancelled = await client.get(path + "/calendar.ics")
    assert (
        f"UID:{event.ics_uid}" in cancelled.text
        and "STATUS:CANCELLED" in cancelled.text
        and "SEQUENCE:1" in cancelled.text
    )


async def test_calendar_edits_advance_sequence_preserve_uid_and_export_url(client, db_session):
    owner = await create_verified_user(db_session)
    profile = await create_organizer(db_session, owner)
    event_id = await create_event(db_session, profile, status="published", title="Before")
    await db_session.commit()
    path = f"/api/v1/events/{event_id}"
    first = (await client.get(path + "/calendar.ics")).text
    uid = next(line for line in first.splitlines() if line.startswith("UID:"))
    for expected, body in [
        (1, {"title": "After"}),
        (1, {"title": "After"}),
        (2, {"description": "Updated description"}),
    ]:
        response = await client.patch(path, json=body, headers=auth_headers(owner))
        assert response.status_code == 200, response.text
        feed = (await client.get(path + "/calendar.ics")).text
        assert uid in feed and f"SEQUENCE:{expected}" in feed
        assert "URL:http" in feed and "X-WR-TIMEZONE:Asia/Almaty" in feed
    await client.post(path + "/cancel", headers=auth_headers(owner))
    feed = (await client.get(path + "/calendar.ics")).text
    assert uid in feed and "SEQUENCE:3" in feed and "STATUS:CANCELLED" in feed
