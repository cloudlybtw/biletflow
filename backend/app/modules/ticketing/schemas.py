import uuid
from datetime import datetime
from typing import Self

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator, model_validator


class TicketTypeCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=10000)
    price_amount: int = Field(default=0, ge=0, le=9_223_372_036_854_775_807)
    quantity_total: int = Field(ge=0, le=2_147_483_647)
    min_per_order: int = Field(default=1, ge=1, le=2_147_483_647)
    max_per_order: int = Field(default=10, ge=1, le=2_147_483_647)
    sales_start_at: AwareDatetime | None = None
    sales_end_at: AwareDatetime | None = None
    is_hidden: bool = False
    display_order: int = Field(default=0, ge=0, le=2_147_483_647)

    @field_validator("name")
    @classmethod
    def not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Name cannot be blank.")
        return value.strip()

    @model_validator(mode="after")
    def valid_limits(self) -> Self:
        if self.max_per_order < self.min_per_order:
            raise ValueError("max_per_order must be >= min_per_order.")
        if self.sales_start_at and self.sales_end_at and self.sales_end_at <= self.sales_start_at:
            raise ValueError("Sales end must be after start.")
        return self


class TicketTypeUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=10000)
    price_amount: int | None = Field(default=None, ge=0, le=9_223_372_036_854_775_807)
    quantity_total: int | None = Field(default=None, ge=0, le=2_147_483_647)
    min_per_order: int | None = Field(default=None, ge=1, le=2_147_483_647)
    max_per_order: int | None = Field(default=None, ge=1, le=2_147_483_647)
    sales_start_at: AwareDatetime | None = None
    sales_end_at: AwareDatetime | None = None
    is_hidden: bool | None = None
    display_order: int | None = Field(default=None, ge=0, le=2_147_483_647)

    @field_validator(
        "name",
        "price_amount",
        "quantity_total",
        "min_per_order",
        "max_per_order",
        "is_hidden",
        "display_order",
        mode="before",
    )
    @classmethod
    def not_null(cls, value):
        if value is None:
            raise ValueError("This field cannot be null.")
        return value


class TicketTypeOut(TicketTypeCreate):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    event_id: uuid.UUID
    currency: str
    quantity_reserved: int
    quantity_sold: int
    created_at: datetime
    updated_at: datetime
