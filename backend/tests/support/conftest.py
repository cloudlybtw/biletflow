from types import SimpleNamespace

import pytest

from app.modules.events.models import EventStatus
from app.modules.users.models import PlatformRole, StaffRole
from tests.factories import (
    create_event,
    create_issued_ticket,
    create_organizer,
    create_staff_assignment,
    create_verified_user,
)


@pytest.fixture
async def ctx(db_session):
    owner = await create_verified_user(db_session)
    profile = await create_organizer(db_session, owner)
    event_id = await create_event(db_session, profile, status=EventStatus.PUBLISHED)
    buyer = await create_verified_user(db_session)
    other = await create_verified_user(db_session)
    staff = await create_verified_user(db_session)
    co = await create_verified_user(db_session)
    scanner = await create_verified_user(db_session)
    admin = await create_verified_user(db_session, platform_role=PlatformRole.PLATFORM_ADMIN)
    assignment = await create_staff_assignment(db_session, event_id, staff, StaffRole.SUPPORT_AGENT)
    await create_staff_assignment(db_session, event_id, co, StaffRole.CO_ORGANIZER)
    await create_staff_assignment(db_session, event_id, scanner, StaffRole.EVENT_ADMIN)
    ticket = await create_issued_ticket(db_session, event_id, buyer)
    await db_session.commit()
    return SimpleNamespace(
        owner=owner,
        profile=profile,
        event_id=event_id,
        buyer=buyer,
        other=other,
        staff=staff,
        co=co,
        scanner=scanner,
        admin=admin,
        assignment=assignment,
        ticket=ticket,
    )
