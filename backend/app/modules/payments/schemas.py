import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

from app.modules.payments.models import PaymentPurpose, PaymentStatus


class PaymentSimulate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    outcome: Literal["success", "failure"]


class PaymentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    order_id: uuid.UUID | None
    activation_id: uuid.UUID | None
    purpose: PaymentPurpose
    provider: str
    provider_payment_ref: str | None
    status: PaymentStatus
    amount: int
    currency: str
    is_simulated: bool
    failure_reason: str | None
    processed_at: datetime | None
    created_at: datetime
    updated_at: datetime
