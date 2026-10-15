import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

from app.modules.activation.models import ActivationStatus
from app.modules.events.models import PaidSalesStatus


class AcceptTerms(BaseModel):
    model_config = ConfigDict(extra="forbid")
    accepted: Literal[True]


class ActivateSales(BaseModel):
    model_config = ConfigDict(extra="forbid")
    payout_account_id: uuid.UUID | None = None


class ActivationChecklist(BaseModel):
    event_id: uuid.UUID
    activation_id: uuid.UUID | None
    status: ActivationStatus | None
    paid_sales_status: PaidSalesStatus
    has_paid_ticket_type: bool
    identity_verified: bool
    payout_account_active: bool
    payout_account_id: uuid.UUID | None
    fee_paid: bool
    fee_amount: int
    fee_payment_id: uuid.UUID | None
    currency: Literal["KZT"] = "KZT"
    simulated: Literal[True] = True
    terms_accepted: bool
    terms_accepted_at: datetime | None
    activated_at: datetime | None
    suspended_at: datetime | None
    suspension_reason: str | None
    event_suspended: bool
    ready_to_activate: bool
