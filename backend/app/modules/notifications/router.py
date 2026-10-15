import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import current_user
from app.core.pagination import Page, Pagination, pagination
from app.db.session import get_session
from app.modules.notifications import service
from app.modules.notifications.schemas import NotificationOut
from app.modules.users.models import User

router = APIRouter(tags=["notifications"])


@router.get(
    "/notifications", response_model=Page[NotificationOut], summary="My in-app notifications"
)
async def inbox(
    unread_only: bool = False,
    page: Pagination = Depends(pagination),
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    items, total = await service.inbox(session, user, page, unread_only)
    return Page(items=items, total=total)


@router.post(
    "/notifications/{notification_id}/read",
    response_model=NotificationOut,
    summary="Mark my in-app notification read (idempotent)",
)
async def mark_read(
    notification_id: uuid.UUID,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    return await service.mark_read(session, user, notification_id)
