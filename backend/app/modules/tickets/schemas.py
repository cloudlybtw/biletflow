import uuid
from datetime import datetime

from pydantic import BaseModel

from app.modules.tickets.models import TicketStatus


class TicketEventOut(BaseModel):
    id: uuid.UUID
    title: str
    starts_at: datetime
    ends_at: datetime
    timezone: str
    venue_name: str | None
    venue_address: str | None
    venue_city: str | None


class TicketOut(BaseModel):
    id: uuid.UUID
    order_id: uuid.UUID
    ticket_code: str
    qr_token: str
    qr_image_url: str
    pdf_url: str
    ticket_type_id: uuid.UUID
    ticket_type_name: str
    attendee_id: uuid.UUID
    attendee_name: str
    attendee_email: str | None
    status: TicketStatus
    seat_id: uuid.UUID | None
    seat_section_label: str | None
    seat_row_label: str | None
    seat_number_label: str | None
    issued_at: datetime
    checked_in_at: datetime | None
    invalidated_at: datetime | None
    event: TicketEventOut
