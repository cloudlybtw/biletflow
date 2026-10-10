import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import require_platform_admin
from app.db.session import get_session
from app.modules.admin import service
from app.modules.admin.schemas import EventModerationOut, SuspensionRequest
from app.modules.users.models import User

router = APIRouter(prefix="/admin/events/{event_id}", tags=["admin moderation"])


@router.post(
    "/suspend",
    response_model=EventModerationOut,
    summary="Suspend all event registrations and payments",
)
async def suspend_event(
    event_id: uuid.UUID,
    data: SuspensionRequest,
    user: User = Depends(require_platform_admin),
    session: AsyncSession = Depends(get_session),
):
    return await service.moderate_event(session, event_id, user, suspend=True, reason=data.reason)


@router.post("/unsuspend", response_model=EventModerationOut)
async def unsuspend_event(
    event_id: uuid.UUID,
    user: User = Depends(require_platform_admin),
    session: AsyncSession = Depends(get_session),
):
    return await service.moderate_event(session, event_id, user, suspend=False)


@router.post(
    "/paid-sales/suspend",
    response_model=EventModerationOut,
    summary="Suspend only paid ticket sales",
)
async def suspend_paid_sales(
    event_id: uuid.UUID,
    data: SuspensionRequest,
    user: User = Depends(require_platform_admin),
    session: AsyncSession = Depends(get_session),
):
    return await service.moderate_paid_sales(
        session, event_id, user, suspend=True, reason=data.reason
    )


@router.post("/paid-sales/unsuspend", response_model=EventModerationOut)
async def unsuspend_paid_sales(
    event_id: uuid.UUID,
    user: User = Depends(require_platform_admin),
    session: AsyncSession = Depends(get_session),
):
    return await service.moderate_paid_sales(session, event_id, user, suspend=False)
