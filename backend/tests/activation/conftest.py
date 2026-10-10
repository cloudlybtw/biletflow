from types import SimpleNamespace

import pytest

from app.modules.events.models import EventStatus
from app.modules.users.models import PlatformRole
from tests.factories import create_event, create_organizer, create_ticket_type, create_verified_user


@pytest.fixture
async def ctx(db_session):
    owner = await create_verified_user(db_session)
    other = await create_verified_user(db_session)
    admin = await create_verified_user(db_session, platform_role=PlatformRole.PLATFORM_ADMIN)
    profile = await create_organizer(db_session, owner)
    event_id = await create_event(db_session, profile, status=EventStatus.PUBLISHED)
    ticket = await create_ticket_type(db_session, event_id)
    await db_session.commit()
    return SimpleNamespace(
        owner=owner,
        other=other,
        admin=admin,
        profile=profile,
        event_id=event_id,
        ticket=ticket,
        path=f"/api/v1/events/{event_id}/paid-sales",
    )
