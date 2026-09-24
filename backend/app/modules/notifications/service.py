import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.notifications.models import Notification, NotificationChannel, NotificationType


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
        related_entity_type=related_entity_type,
        related_entity_id=related_entity_id,
    )
    session.add(notification)
    await session.flush()
    return notification
