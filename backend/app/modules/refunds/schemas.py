import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.modules.refunds.models import RefundStatus


class ReversalIn(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    reason: str | None = Field(default=None, min_length=1, max_length=2000)


class CancellationOut(BaseModel):
    order_id: uuid.UUID
    status: Literal["cancelled"] = "cancelled"
    ticket_ids: list[uuid.UUID]


class RefundOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    payment_id: uuid.UUID
    order_id: uuid.UUID
    initiated_by_user_id: uuid.UUID | None
    amount: int
    currency: str
    reason: str | None
    status: RefundStatus
    provider_refund_ref: str | None
    simulated: Literal[True] = Field(validation_alias="is_simulated")
    processed_at: datetime | None
    created_at: datetime
    updated_at: datetime
