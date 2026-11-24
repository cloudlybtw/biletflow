import uuid
from decimal import Decimal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, Field, field_validator


class VenueOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    name: str
    address_line: str
    city: str
    country: str
    latitude: Decimal | None
    longitude: Decimal | None
    timezone: str
    is_predefined: bool


class PriceCategoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    code: str
    name: str
    display_color: str | None


class SeatOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    seat_number: str
    price_category_id: uuid.UUID | None
    is_accessible: bool
    position_x: Decimal
    position_y: Decimal


class RowOut(BaseModel):
    id: uuid.UUID
    label: str
    display_order: int
    seats: list[SeatOut]


class SectionOut(BaseModel):
    id: uuid.UUID
    name: str
    display_order: int
    rows: list[RowOut]


class VenueDetail(VenueOut):
    price_categories: list[PriceCategoryOut]
    sections: list[SectionOut]


class VenueCreate(BaseModel):
    """A venue an organizer adds from an address search (no seat map)."""

    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=200)
    address_line: str = Field(min_length=1, max_length=500)
    city: str = Field(min_length=1, max_length=120)
    country: str = Field(default="KZ", min_length=2, max_length=2)
    latitude: Decimal | None = Field(default=None, ge=-90, le=90)
    longitude: Decimal | None = Field(default=None, ge=-180, le=180)
    timezone: str = "Asia/Almaty"

    @field_validator("name", "address_line", "city")
    @classmethod
    def not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Cannot be blank.")
        return value.strip()

    @field_validator("country")
    @classmethod
    def upper_country(cls, value: str) -> str:
        return value.upper()

    @field_validator("latitude", "longitude")
    @classmethod
    def six_places(cls, value: Decimal | None) -> Decimal | None:
        # Column is NUMERIC(9, 6); geocoders return more digits than that.
        return None if value is None else round(value, 6)

    @field_validator("timezone")
    @classmethod
    def valid_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise ValueError("Unknown IANA timezone.") from exc
        return value
