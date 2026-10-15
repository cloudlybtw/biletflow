import uuid
from datetime import datetime

from pydantic import BaseModel

from app.modules.notifications.models import NotificationStatus, NotificationType


class NotificationOut(BaseModel):
    id: uuid.UUID
    type: NotificationType
    title: str
    body: str
    related_entity_type: str | None
    related_entity_id: str | None
    status: NotificationStatus
    read_at: datetime | None
    created_at: datetime
