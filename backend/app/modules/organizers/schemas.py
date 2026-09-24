import uuid
from datetime import datetime
from typing import Annotated, Literal

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    StringConstraints,
    model_validator,
)

from app.modules.organizers.models import PayoutAccountStatus, VerificationStatus
from app.modules.users.schemas import FullName, Phone

DisplayName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
Description = Annotated[str, StringConstraints(strip_whitespace=True, max_length=5000)]


def _normalize_account_ref(value: str) -> str:
    normalized = "".join(value.split()).upper()
    if not normalized.isalnum() or not 4 <= len(normalized) <= 34:
        raise ValueError("must be 4-34 letters and digits (spaces are ignored)")
    return normalized


AccountRef = Annotated[str, AfterValidator(_normalize_account_ref)]


class OrganizerProfileCreate(BaseModel):
    display_name: DisplayName
    contact_email: EmailStr | None = Field(
        default=None, description="Defaults to the account email."
    )
    contact_phone: Phone | None = None
    description: Description | None = None


class OrganizerProfileUpdate(BaseModel):
    """Only the fields sent are changed; `contact_phone`/`description` accept `null`."""

    display_name: DisplayName | None = None
    contact_email: EmailStr | None = None
    contact_phone: Phone | None = None
    description: Description | None = None

    @model_validator(mode="after")
    def _required_fields_not_null(self) -> "OrganizerProfileUpdate":
        for field in ("display_name", "contact_email"):
            if field in self.model_fields_set and getattr(self, field) is None:
                raise ValueError(f"{field} cannot be null")
        return self


class OrganizerProfileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    display_name: str
    contact_email: str
    contact_phone: str | None
    description: str | None
    verification_status: VerificationStatus
    verified_at: datetime | None
    created_at: datetime


class IdentityVerificationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    verification_status: VerificationStatus
    verified_at: datetime | None
    simulated: Literal[True] = Field(
        default=True, description="Always true: no real identity check (SRS §3.2)."
    )


class PayoutAccountCreate(BaseModel):
    account_holder_name: FullName
    external_account_ref: AccountRef = Field(
        description="Simulated IBAN or account number, e.g. `KZ86125KZT5004100100`. "
        "Nothing is ever paid out to it."
    )


class PayoutAccountOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    provider: str
    external_account_ref: str
    account_holder_name: str
    currency: str
    status: PayoutAccountStatus
    is_default: bool
    simulated: Literal[True] = Field(
        default=True, description="Always true: a demo account, no real money moves."
    )
    created_at: datetime
