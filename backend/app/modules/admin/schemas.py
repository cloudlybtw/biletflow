import uuid
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, StringConstraints

from app.modules.events.models import EventStatus, PaidSalesStatus


class SuspensionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)]


class EventModerationOut(BaseModel):
    event_id: uuid.UUID
    status: EventStatus
    paid_sales_status: PaidSalesStatus
    is_suspended: bool
    suspended_at: datetime | None
    suspended_by: uuid.UUID | None
    suspension_reason: str | None
