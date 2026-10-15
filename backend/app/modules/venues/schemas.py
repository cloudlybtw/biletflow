import uuid
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


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
