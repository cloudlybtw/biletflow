import uuid
from datetime import datetime
from typing import Self

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator, model_validator

from app.modules.campaigns.models import CampaignStatus, DiscountType


class CampaignFields(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=200)
    discount_type: DiscountType
    discount_value: int = Field(gt=0, le=9_223_372_036_854_775_807)
    starts_at: AwareDatetime | None = None
    ends_at: AwareDatetime | None = None
    max_redemptions: int | None = Field(default=None, gt=0, le=2_147_483_647)
    ticket_type_ids: list[uuid.UUID] = Field(default_factory=list, max_length=100)

    @field_validator("name")
    @classmethod
    def not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Name cannot be blank.")
        return value.strip()

    @model_validator(mode="after")
    def valid_values(self) -> Self:
        if self.discount_type == DiscountType.PERCENT and self.discount_value > 100:
            raise ValueError("Percent must be <= 100.")
        if self.starts_at and self.ends_at and self.ends_at <= self.starts_at:
            raise ValueError("ends_at must be after starts_at.")
        if len(set(self.ticket_type_ids)) != len(self.ticket_type_ids):
            raise ValueError("Duplicate ticket types are not allowed.")
        return self


class CodeCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    code: str | None = Field(
        default=None, min_length=3, max_length=40, pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]*$"
    )

    @field_validator("code")
    @classmethod
    def normalize(cls, value: str | None) -> str | None:
        return value.upper() if value else None


class CampaignCreate(CampaignFields):
    code: str | None = None

    @field_validator("code")
    @classmethod
    def valid_code(cls, value: str | None) -> str | None:
        return CodeCreate(code=value).code


class CampaignUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str | None = Field(default=None, min_length=1, max_length=200)
    discount_type: DiscountType | None = None
    discount_value: int | None = Field(default=None, gt=0, le=9_223_372_036_854_775_807)
    starts_at: AwareDatetime | None = None
    ends_at: AwareDatetime | None = None
    max_redemptions: int | None = Field(default=None, gt=0, le=2_147_483_647)
    ticket_type_ids: list[uuid.UUID] | None = Field(default=None, max_length=100)

    @field_validator("name", "discount_type", "discount_value", "ticket_type_ids", mode="before")
    @classmethod
    def not_null(cls, value):
        if value is None:
            raise ValueError("This field cannot be null.")
        return value


class CodeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    campaign_id: uuid.UUID
    code: str
    is_active: bool
    created_at: datetime


class CampaignOut(CampaignFields):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    event_id: uuid.UUID
    currency: str
    redemption_count: int
    status: CampaignStatus
    created_by: uuid.UUID | None
    created_at: datetime
    updated_at: datetime
    promo_codes: list[CodeOut] = Field(default_factory=list)


class QRCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    promo_code_id: uuid.UUID | None = None


class QROut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    campaign_id: uuid.UUID
    promo_code_id: uuid.UUID
    token: str
    target_url: str
    image_url: str | None
    label: str | None
    scan_count: int
    created_at: datetime


class LinkOut(BaseModel):
    event_slug: str
    promo_code: str
    campaign_id: uuid.UUID


class CartItem(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ticket_type_id: uuid.UUID
    quantity: int = Field(gt=0, le=2_147_483_647)


class PromoValidate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    code: str = Field(min_length=1, max_length=40)
    items: list[CartItem] = Field(min_length=1, max_length=100)

    @model_validator(mode="after")
    def no_duplicates(self) -> Self:
        ids = [item.ticket_type_id for item in self.items]
        if len(set(ids)) != len(ids):
            raise ValueError("Combine duplicate ticket types into one cart line.")
        return self


class DiscountPreview(BaseModel):
    campaign_id: uuid.UUID
    promo_code_id: uuid.UUID
    currency: str = "KZT"
    subtotal_amount: int
    eligible_subtotal_amount: int
    discount_amount: int
    total_amount: int
