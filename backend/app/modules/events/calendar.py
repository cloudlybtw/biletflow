"""Calendar feeds contain public event information, never attendee data."""

import uuid
from datetime import UTC, datetime
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.deps import optional_current_user
from app.db.session import get_session
from app.modules.events.models import EventStatus, EventVisibility
from app.modules.events.service import get_event, visible_event
from app.modules.users.models import User
from app.modules.venues.models import Venue

router = APIRouter(tags=["calendar"])


def escape(value):
    return (
        str(value or "")
        .replace("\\", "\\\\")
        .replace("\r", "")
        .replace("\n", "\\n")
        .replace(";", "\\;")
        .replace(",", "\\,")
    )


def fold(line):
    chunks, current = [], ""
    for character in line:
        if len((current + character).encode()) > 75:
            chunks.append(current)
            current = " "
        current += character
    return "\r\n".join([*chunks, current])


def event_url(event):
    return get_settings().web_base_url.rstrip("/") + "/#/events/" + event.slug


def stamp(value):
    return value.astimezone(UTC).strftime("%Y%m%dT%H%M%SZ")


async def calendar_event(session, event_id, user):
    event = await get_event(session, event_id)
    if not (
        event.status == EventStatus.CANCELLED
        and event.visibility != EventVisibility.PRIVATE
        and not event.is_suspended
    ):
        await visible_event(session, event_id, user)
    venue = await session.get(Venue, event.venue_id) if event.venue_id else None
    location = f"{venue.name}, {venue.address_line}, {venue.city}" if venue else ""
    return event, location


@router.get("/events/{event_id}/calendar.ics", response_class=Response)
async def calendar(
    event_id: uuid.UUID,
    user: User | None = Depends(optional_current_user),
    session: AsyncSession = Depends(get_session),
):
    event, location = await calendar_event(session, event_id, user)
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//BiletFlow//Events//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        f"X-WR-TIMEZONE:{escape(event.timezone)}",
        "BEGIN:VEVENT",
        f"UID:{escape(event.ics_uid)}",
        f"SEQUENCE:{event.ics_sequence}",
        f"DTSTAMP:{stamp(datetime.now(UTC))}",
        f"DTSTART:{stamp(event.starts_at)}",
        f"DTEND:{stamp(event.ends_at)}",
        f"SUMMARY:{escape(event.title)}",
        f"DESCRIPTION:{escape(event.description)}",
        f"LOCATION:{escape(location)}",
        f"URL:{escape(event_url(event))}",
        f"STATUS:{'CANCELLED' if event.status == EventStatus.CANCELLED else 'CONFIRMED'}",
        "END:VEVENT",
        "END:VCALENDAR",
    ]
    return Response(
        "\r\n".join(fold(line) for line in lines) + "\r\n",
        media_type="text/calendar",
        headers={"Content-Disposition": 'attachment; filename="event.ics"'},
    )


@router.get("/events/{event_id}/calendar-links")
async def links(
    event_id: uuid.UUID,
    user: User | None = Depends(optional_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, str]:
    event, location = await calendar_event(session, event_id, user)
    return {
        "ics": f"/api/v1/events/{event_id}/calendar.ics",
        "google": "https://calendar.google.com/calendar/render?"
        + urlencode(
            {
                "action": "TEMPLATE",
                "text": event.title,
                "dates": stamp(event.starts_at) + "/" + stamp(event.ends_at),
                "details": (event.description or "") + "\n" + event_url(event),
                "ctz": event.timezone,
                "location": location,
            }
        ),
        "outlook": "https://outlook.live.com/calendar/0/deeplink/compose?"
        + urlencode(
            {
                "subject": event.title,
                "startdt": event.starts_at.isoformat(),
                "enddt": event.ends_at.isoformat(),
                "body": (event.description or "") + "\n" + event_url(event),
                "location": location,
            }
        ),
    }
