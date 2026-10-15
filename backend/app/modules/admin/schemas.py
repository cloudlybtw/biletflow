import uuid
from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from app.modules.activation.models import ActivationStatus
from app.modules.events.models import EventStatus, PaidSalesStatus
from app.modules.users.models import PlatformRole, UserStatus


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


class AdminUserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    email: str
    full_name: str
    phone: str | None
    locale: str
    platform_role: PlatformRole
    status: UserStatus
    email_verified_at: datetime | None
    last_login_at: datetime | None
    created_at: datetime
    updated_at: datetime


class AdminActivationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    event_id: uuid.UUID
    organizer_profile_id: uuid.UUID
    payout_account_id: uuid.UUID | None
    fee_payment_id: uuid.UUID | None
    fee_amount: int
    currency: str
    status: ActivationStatus
    identity_verified_at: datetime | None
    terms_accepted_at: datetime | None
    activated_at: datetime | None
    suspended_at: datetime | None
    suspended_by: uuid.UUID | None
    suspension_reason: str | None
    created_at: datetime
    updated_at: datetime
    simulated: Literal[True] = True


class SettingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    key: str
    value: int | float
    updated_by: uuid.UUID | None
    updated_at: datetime


class SettingsUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)
    activation_fee_kzt: int | None = Field(default=None, ge=0, le=9_223_372_036_854_775_807)
    processing_fee_percent: int | float | None = Field(default=None, ge=0, le=100)
    order_hold_minutes: int | None = Field(default=None, ge=1, le=10080)
    seat_hold_minutes: int | None = Field(default=None, ge=1, le=10080)

    @model_validator(mode="after")
    def not_empty_or_null(self):
        if not self.model_fields_set or any(
            getattr(self, key) is None for key in self.model_fields_set
        ):
            raise ValueError("Supply at least one setting; settings cannot be null.")
        return self
