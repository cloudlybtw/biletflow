import uuid
from datetime import datetime
from typing import Self

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

from app.modules.orders.models import OrderStatus
from app.modules.payments.schemas import PaymentOut


class AttendeeInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    full_name: str = Field(min_length=1, max_length=200)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=50)

    @field_validator("full_name")
    @classmethod
    def not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Attendee name cannot be blank.")
        return value.strip()


class CheckoutItem(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ticket_type_id: uuid.UUID
    quantity: int = Field(default=1, ge=1, le=1000)
    attendees: list[AttendeeInput] | None = Field(default=None, max_length=1000)
    seat_hold_ids: list[uuid.UUID] = Field(default_factory=list, max_length=1000)

    @model_validator(mode="after")
    def match_quantity(self) -> Self:
        if self.attendees is not None and len(self.attendees) != self.quantity:
            raise ValueError("Provide exactly one attendee per ticket or omit attendees.")
        if self.seat_hold_ids and len(self.seat_hold_ids) != self.quantity:
            raise ValueError("Provide exactly one seat hold per assigned ticket.")
        return self


class CheckoutCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: list[CheckoutItem] = Field(min_length=1, max_length=100)
    promo_code: str | None = Field(default=None, min_length=1, max_length=40)

    @model_validator(mode="after")
    def distinct_lines_and_holds(self) -> Self:
        if len({item.ticket_type_id for item in self.items}) != len(self.items):
            raise ValueError("Combine quantities for each ticket type into a single line.")
        holds = [hold for item in self.items for hold in item.seat_hold_ids]
        if len(set(holds)) != len(holds):
            raise ValueError("A seat hold can be used only once.")
        if sum(item.quantity for item in self.items) > 1000:
            raise ValueError("A checkout request may contain at most 1000 tickets.")
        return self


class AttendeeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    full_name: str
    email: str | None
    phone: str | None


class OrderItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    ticket_type_id: uuid.UUID
    seat_id: uuid.UUID | None
    quantity: int
    unit_price_amount: int
    discount_amount: int
    line_total: int
    attendees: list[AttendeeOut] = Field(default_factory=list)


class OrderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    order_number: str
    event_id: uuid.UUID
    buyer_email: str
    buyer_name: str
    buyer_phone: str | None
    status: OrderStatus
    currency: str
    subtotal_amount: int
    discount_amount: int
    fee_amount: int
    total_amount: int
    promo_code_id: uuid.UUID | None
    campaign_id: uuid.UUID | None
    is_simulated: bool
    placed_at: datetime | None
    expires_at: datetime | None
    created_at: datetime
    updated_at: datetime


class OrderDetail(OrderOut):
    items: list[OrderItemOut]
    payments: list[PaymentOut]
    ticket_ids: list[uuid.UUID]
