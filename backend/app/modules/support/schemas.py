import uuid
from datetime import datetime
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.modules.support.models import CaseStatus, CaseType, Category, SenderRole


class CaseCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    case_type: CaseType = CaseType.ATTENDEE
    category: Category
    subject: str = Field(min_length=1, max_length=200)
    body: str = Field(min_length=1, max_length=10000)
    event_id: uuid.UUID | None = None
    order_id: uuid.UUID | None = None
    ticket_id: uuid.UUID | None = None

    @model_validator(mode="after")
    def valid_context(self) -> Self:
        if self.case_type == CaseType.ATTENDEE and not any(
            (self.event_id, self.order_id, self.ticket_id)
        ):
            raise ValueError("Attendee cases require event, order, or ticket context.")
        if self.case_type == CaseType.ORGANIZER and (self.order_id or self.ticket_id):
            raise ValueError("Organizer platform cases accept an optional owned event only.")
        return self


class MessageCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    body: str = Field(min_length=1, max_length=10000)
    is_internal_note: bool = False


class AssignmentUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    assigned_to_user_id: uuid.UUID | None


class StatusUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: CaseStatus


class CaseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    case_number: str
    case_type: CaseType
    category: Category
    subject: str
    opened_by_user_id: uuid.UUID
    event_id: uuid.UUID | None
    order_id: uuid.UUID | None
    ticket_id: uuid.UUID | None
    status: CaseStatus
    assigned_to_user_id: uuid.UUID | None
    last_message_at: datetime | None
    resolved_at: datetime | None
    created_at: datetime
    updated_at: datetime


class MessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    case_id: uuid.UUID
    sender_user_id: uuid.UUID
    sender_role: SenderRole
    body: str
    is_internal_note: bool
    created_at: datetime
