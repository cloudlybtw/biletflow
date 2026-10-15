import uuid
from datetime import datetime
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.modules.checkin.models import CheckInAction, CheckInResult, CheckInSource
from app.modules.tickets.models import TicketStatus


class ScanIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    token: str | None = Field(default=None, min_length=1, max_length=4096)
    ticket_id: uuid.UUID | None = None
    device_id: str | None = Field(default=None, max_length=200)

    @model_validator(mode="after")
    def exactly_one_input(self) -> Self:
        if (self.token is None) == (self.ticket_id is None):
            raise ValueError("Provide exactly one of token (QR scan) or ticket_id (manual search).")
        return self


class ReverseIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    device_id: str | None = Field(default=None, max_length=200)
    notes: str | None = Field(default=None, max_length=2000)


class CheckInTicketOut(BaseModel):
    ticket_id: uuid.UUID
    ticket_code: str
    attendee_name: str
    attendee_email: str | None
    ticket_type_id: uuid.UUID
    ticket_type_name: str
    status: TicketStatus
    checked_in_at: datetime | None
    seat_section_label: str | None
    seat_row_label: str | None
    seat_number_label: str | None
    check_in_record_id: uuid.UUID | None


class CheckInOut(BaseModel):
    record_id: uuid.UUID
    event_id: uuid.UUID
    action: CheckInAction
    result: CheckInResult
    source: CheckInSource
    scanned_at: datetime
    reverses_record_id: uuid.UUID | None
    ticket: CheckInTicketOut | None


class CountersOut(BaseModel):
    registered: int
    checked_in: int
