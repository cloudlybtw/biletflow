import uuid

from fastapi import APIRouter, Depends
from pydantic import AwareDatetime
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import (
    EventAccess,
    current_user,
    require_event_role,
    require_platform_admin,
    require_support_case,
)
from app.core.pagination import Page, Pagination, pagination
from app.db.session import get_session
from app.modules.support import service
from app.modules.support.models import CaseStatus, CaseType, Category
from app.modules.support.schemas import (
    AssignmentUpdate,
    CaseCreate,
    CaseOut,
    MessageCreate,
    MessageOut,
    StatusUpdate,
)
from app.modules.support.service import CaseAccess
from app.modules.users.models import StaffRole, User

router = APIRouter(tags=["support"])
event_support = require_event_role(
    StaffRole.CO_ORGANIZER, StaffRole.SUPPORT_AGENT, allow_platform_admin=True
)


@router.post(
    "/support/cases",
    response_model=CaseOut,
    status_code=201,
    summary="Open an attendee or organizer support case",
)
async def create(
    data: CaseCreate,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    return await service.create(session, user, data)


@router.get("/support/cases", response_model=Page[CaseOut], summary="My support cases")
async def mine(
    status: CaseStatus | None = None,
    page: Pagination = Depends(pagination),
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    items, total = await service.my_cases(session, user, page, status)
    return Page(items=items, total=total)


@router.get(
    "/events/{event_id}/support/cases",
    response_model=Page[CaseOut],
    summary="Event attendee support cases",
)
async def event_cases(
    event_id: uuid.UUID,
    status: CaseStatus | None = None,
    page: Pagination = Depends(pagination),
    access: EventAccess = Depends(event_support),
    session: AsyncSession = Depends(get_session),
):
    items, total = await service.event_cases(session, access.event_id, page, status)
    return Page(items=items, total=total)


@router.get(
    "/admin/support/cases",
    response_model=Page[CaseOut],
    summary="Platform support inbox and case moderation",
)
async def admin_cases(
    status: CaseStatus | None = None,
    case_type: CaseType | None = None,
    event_id: uuid.UUID | None = None,
    order_id: uuid.UUID | None = None,
    category: Category | None = None,
    page: Pagination = Depends(pagination),
    user: User = Depends(require_platform_admin),
    session: AsyncSession = Depends(get_session),
):
    items, total = await service.admin_cases(
        session, page, status, case_type, event_id=event_id, order_id=order_id, category=category
    )
    return Page(items=items, total=total)


@router.get(
    "/support/cases/{case_id}", response_model=CaseOut, summary="Read an authorized support case"
)
async def detail(access: CaseAccess = Depends(require_support_case)):
    return CaseOut.model_validate(access.case)


@router.get(
    "/support/cases/{case_id}/messages",
    response_model=Page[MessageOut],
    summary="Poll case messages with an inclusive UTC timestamp",
)
async def messages(
    since: AwareDatetime | None = None,
    page: Pagination = Depends(pagination),
    access: CaseAccess = Depends(require_support_case),
    session: AsyncSession = Depends(get_session),
):
    items, total = await service.messages(session, access, page, since)
    return Page(items=items, total=total)


@router.post(
    "/support/cases/{case_id}/messages",
    response_model=MessageOut,
    status_code=201,
    summary="Add a public reply or staff-only internal note",
)
async def post_message(
    data: MessageCreate,
    access: CaseAccess = Depends(require_support_case),
    session: AsyncSession = Depends(get_session),
):
    return await service.post_message(session, access, data)


@router.patch(
    "/support/cases/{case_id}/assignment",
    response_model=CaseOut,
    summary="Assign or unassign a support case",
)
async def assign(
    data: AssignmentUpdate,
    access: CaseAccess = Depends(require_support_case),
    session: AsyncSession = Depends(get_session),
):
    return await service.assign(session, access, data.assigned_to_user_id)


@router.patch(
    "/support/cases/{case_id}/status",
    response_model=CaseOut,
    summary="Change a support case status (idempotent)",
)
async def status(
    data: StatusUpdate,
    access: CaseAccess = Depends(require_support_case),
    session: AsyncSession = Depends(get_session),
):
    return await service.change_status(session, access, data.status)
