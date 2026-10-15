import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NOT_FOUND, AppError
from app.core.pagination import Pagination
from app.db.pagination import read_page
from app.modules.notifications.models import (
    Notification,
    NotificationChannel,
    NotificationStatus,
    NotificationType,
)
from app.modules.notifications.schemas import NotificationOut
from app.modules.notifications.templates import render
from app.modules.users.models import User


async def enqueue(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    type: NotificationType,
    channel: NotificationChannel,
    template_key: str,
    payload: dict[str, Any] | None = None,
    related_entity_type: str | None = None,
    related_entity_id: str | None = None,
) -> Notification:
    """Queue a notification in the caller's transaction; the sender job delivers it."""
    notification = Notification(
        user_id=user_id,
        type=type,
        channel=channel,
        template_key=template_key,
        payload=payload or {},
        **(
            {"status": NotificationStatus.SENT, "sent_at": datetime.now(UTC)}
            if channel == NotificationChannel.IN_APP
            else {}
        ),
        related_entity_type=related_entity_type,
        related_entity_id=related_entity_id,
    )
    session.add(notification)
    await session.flush()
    return notification


def output(row: Notification, locale: str) -> NotificationOut:
    title, body = render(row.type, row.payload, locale)
    return NotificationOut(
        id=row.id,
        type=row.type,
        title=title,
        body=body,
        related_entity_type=row.related_entity_type,
        related_entity_id=row.related_entity_id,
        status=row.status,
        read_at=row.read_at,
        created_at=row.created_at,
    )


async def inbox(session: AsyncSession, user: User, page: Pagination, unread_only: bool):
    query = select(Notification).where(
        Notification.user_id == user.id, Notification.channel == NotificationChannel.IN_APP
    )
    if unread_only:
        query = query.where(Notification.read_at.is_(None))
    rows, total = await read_page(
        session, query.order_by(Notification.created_at.desc(), Notification.id), page
    )
    return [output(row, user.locale) for row in rows], total


async def mark_read(session: AsyncSession, user: User, notification_id: uuid.UUID):
    row = await session.scalar(
        update(Notification)
        .where(
            Notification.id == notification_id,
            Notification.user_id == user.id,
            Notification.channel == NotificationChannel.IN_APP,
        )
        .values(
            status=NotificationStatus.READ, read_at=func.coalesce(Notification.read_at, func.now())
        )
        .returning(Notification)
        .execution_options(populate_existing=True)
    )
    if row is None:
        raise AppError(NOT_FOUND, "Notification not found.", 404)
    result = output(row, user.locale)
    await session.commit()
    return result
