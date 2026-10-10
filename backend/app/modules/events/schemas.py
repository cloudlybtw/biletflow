import uuid
from datetime import datetime
from typing import Self
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    field_validator,
    model_validator,
)

from app.modules.events.models import EventStatus, EventVisibility, PaidSalesStatus, SeatingMode
from app.modules.users.models import StaffRole


class EventFields(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=20000)
    timezone: str = "Asia/Almaty"
    starts_at: AwareDatetime
    ends_at: AwareDatetime
    venue_id: uuid.UUID | None = None
    category_id: uuid.UUID | None = None
    visibility: EventVisibility = EventVisibility.PUBLIC
    seating_mode: SeatingMode = SeatingMode.GENERAL_ADMISSION
    capacity: int | None = Field(default=None, gt=0, le=2_147_483_647)
    registration_opens_at: AwareDatetime | None = None
    registration_closes_at: AwareDatetime | None = None
    refund_policy: str | None = Field(default=None, max_length=10000)

    @field_validator("title")
    @classmethod
    def title_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Title cannot be blank.")
        return value.strip()

    @field_validator("timezone")
    @classmethod
    def valid_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise ValueError("Unknown IANA timezone.") from exc
        return value

    @model_validator(mode="after")
    def valid_windows(self) -> Self:
        if self.ends_at <= self.starts_at:
            raise ValueError("ends_at must be after starts_at.")
        if (
            self.registration_opens_at
            and self.registration_closes_at
            and self.registration_closes_at <= self.registration_opens_at
        ):
            raise ValueError("Registration close must be after open.")
        if self.seating_mode == SeatingMode.ASSIGNED and self.venue_id is None:
            raise ValueError("Assigned seating requires a venue.")
        return self


class EventCreate(EventFields):
    pass


class EventUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=20000)
    timezone: str | None = None
    starts_at: AwareDatetime | None = None
    ends_at: AwareDatetime | None = None
    venue_id: uuid.UUID | None = None
    category_id: uuid.UUID | None = None
    visibility: EventVisibility | None = None
    seating_mode: SeatingMode | None = None
    capacity: int | None = Field(default=None, gt=0, le=2_147_483_647)
    registration_opens_at: AwareDatetime | None = None
    registration_closes_at: AwareDatetime | None = None
    refund_policy: str | None = Field(default=None, max_length=10000)

    @field_validator(
        "title", "timezone", "starts_at", "ends_at", "visibility", "seating_mode", mode="before"
    )
    @classmethod
    def not_null(cls, value):
        if value is None:
            raise ValueError("This field cannot be null.")
        return value


class EventOut(EventFields):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    organizer_profile_id: uuid.UUID
    slug: str
    status: EventStatus
    paid_sales_status: PaidSalesStatus
    is_suspended: bool
    published_at: datetime | None
    cancelled_at: datetime | None
    created_at: datetime
    updated_at: datetime
    classification: str = "Upcoming"


class CategoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    slug: str
    name_kk: str
    name_ru: str
    name_en: str
    display_order: int


class ImageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    event_id: uuid.UUID
    url: str
    alt_text: str | None
    sort_order: int
    is_cover: bool


class ImageUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    is_cover: bool | None = None
    alt_text: str | None = Field(default=None, max_length=500)
    sort_order: int | None = Field(default=None, ge=0, le=2_147_483_647)

    @field_validator("is_cover", "sort_order", mode="before")
    @classmethod
    def not_null(cls, value):
        if value is None:
            raise ValueError("This field cannot be null.")
        return value


class StaffCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: EmailStr
    role: StaffRole


class StaffOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    event_id: uuid.UUID
    user_id: uuid.UUID
    role: StaffRole
    assigned_by: uuid.UUID | None
    created_at: datetime
    revoked_at: datetime | None
