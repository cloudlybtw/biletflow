import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.modules.checkin.models import CheckInAction, CheckInResult, CheckInSource
from app.modules.orders.schemas import OrderDetail, OrderOut
from app.modules.tickets.models import TicketStatus


class HistoryOut(BaseModel):
    id: int
    occurred_at: datetime
    actor_user_id: uuid.UUID | None
    actor_name: str | None
    actor_role: str | None
    action_type: str
    entity_type: str
    entity_id: str
    summary: str


class ManagedOrderOut(OrderOut):
    simulated: bool = True


class ManagedOrderDetail(OrderDetail):
    simulated: bool = True


class ManagedTicketOut(BaseModel):
    id: uuid.UUID
    order_id: uuid.UUID
    ticket_code: str
    ticket_type_id: uuid.UUID
    ticket_type_name: str
    attendee_id: uuid.UUID
    attendee_name: str
    attendee_email: str | None
    status: TicketStatus
    seat_section_label: str | None
    seat_row_label: str | None
    seat_number_label: str | None
    issued_at: datetime
    checked_in_at: datetime | None
    invalidated_at: datetime | None


class ManagedCheckInOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    event_id: uuid.UUID
    ticket_id: uuid.UUID | None
    scanned_by_user_id: uuid.UUID | None
    action: CheckInAction
    result: CheckInResult
    source: CheckInSource
    reverses_record_id: uuid.UUID | None
    scanned_at: datetime
