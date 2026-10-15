from types import SimpleNamespace

import pytest

from app.modules.events.models import EventStatus, PaidSalesStatus
from app.modules.users.models import StaffRole
from tests.factories import (
    create_event,
    create_organizer,
    create_staff_assignment,
    create_ticket_type,
    create_verified_user,
)


@pytest.fixture
async def context(db_session):
    owner = await create_verified_user(db_session)
    profile = await create_organizer(db_session, owner)
    event_id = await create_event(
        db_session, profile, status=EventStatus.PUBLISHED, paid_sales_status=PaidSalesStatus.ACTIVE
    )
    ticket_type = await create_ticket_type(db_session, event_id, price_amount=1000)
    buyer = await create_verified_user(db_session)
    other_buyer = await create_verified_user(db_session)
    co = await create_verified_user(db_session)
    assignment = await create_staff_assignment(db_session, event_id, co, StaffRole.CO_ORGANIZER)
    await db_session.commit()
    return SimpleNamespace(
        owner=owner,
        profile=profile,
        event_id=event_id,
        ticket_type=ticket_type,
        buyer=buyer,
        other_buyer=other_buyer,
        co=co,
        assignment=assignment,
    )
