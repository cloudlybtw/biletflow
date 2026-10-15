import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import EventAccess, require_event_role
from app.core.pagination import Page, Pagination, pagination
from app.db.session import get_session
from app.modules.checkin import service
from app.modules.checkin.schemas import CheckInOut, CheckInTicketOut, CountersOut, ReverseIn, ScanIn
from app.modules.users.models import StaffRole

router = APIRouter(tags=["checkin"])
checkin_access = require_event_role(StaffRole.EVENT_ADMIN, StaffRole.CO_ORGANIZER)
checkin_read_access = require_event_role(
    StaffRole.EVENT_ADMIN, StaffRole.CO_ORGANIZER, allow_platform_admin=True
)


@router.post(
    "/checkin/scan",
    response_model=CheckInOut,
    status_code=201,
    summary="Scan a ticket or manually admit an attendee",
)
async def scan(
    data: ScanIn,
    access: EventAccess = Depends(checkin_access),
    session: AsyncSession = Depends(get_session),
):
    return await service.scan(session, access, data)


@router.get(
    "/events/{event_id}/checkin/attendees",
    response_model=Page[CheckInTicketOut],
    summary="Search event attendees by name, email or ticket code",
)
async def search(
    q: Annotated[str | None, Query(max_length=200)] = None,
    page: Pagination = Depends(pagination),
    access: EventAccess = Depends(checkin_read_access),
    session: AsyncSession = Depends(get_session),
):
    items, total = await service.search(session, access, page, q)
    return Page(items=items, total=total)


@router.post(
    "/events/{event_id}/checkin/records/{record_id}/reverse",
    response_model=CheckInOut,
    status_code=201,
    summary="Reverse a successful ticket check-in",
)
async def reverse(
    record_id: uuid.UUID,
    data: ReverseIn,
    access: EventAccess = Depends(checkin_access),
    session: AsyncSession = Depends(get_session),
):
    return await service.reverse(session, access, record_id, data)


@router.get(
    "/events/{event_id}/checkin/counters",
    response_model=CountersOut,
    summary="Get current registered and checked-in ticket counts",
)
async def counters(
    access: EventAccess = Depends(checkin_read_access),
    session: AsyncSession = Depends(get_session),
):
    return await service.counters(session, access)
