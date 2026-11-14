import uuid
from datetime import UTC, datetime
from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import EventAccess, require_event_role, require_platform_admin, require_verified
from app.core.errors import AppError
from app.core.pagination import Page, Pagination, pagination
from app.core.reporting import ReportFilters
from app.db.session import get_session
from app.modules.analytics import service as analytics
from app.modules.events.service import get_event, visible_event
from app.modules.history.service import record
from app.modules.notifications.models import NotificationChannel, NotificationType
from app.modules.notifications.service import enqueue
from app.modules.operations.models import EventReport, SimulatedPayout
from app.modules.users.models import StaffRole, User

router = APIRouter(tags=["operational workflows"])
manager = require_event_role(StaffRole.CO_ORGANIZER, allow_platform_admin=True)
owner = require_event_role()


class PayoutOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    event_id: uuid.UUID
    organizer_user_id: uuid.UUID
    amount: int
    status: Literal["requested", "processing", "paid", "failed"]
    note: str
    simulated: Literal[True] = True
    currency: Literal["KZT"] = "KZT"
    created_at: datetime
    updated_at: datetime


class PayoutUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    status: Literal["processing", "paid", "failed"]
    note: str = Field(min_length=1, max_length=1000)


class ReportCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    reason: str = Field(min_length=1, max_length=2000)


class ReportUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    status: Literal["reviewing", "resolved", "dismissed"]
    resolution: str = Field(min_length=1, max_length=2000)


class ReportOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    event_id: uuid.UUID
    reporter_user_id: uuid.UUID
    reason: str
    status: str
    resolution: str
    reviewed_by: uuid.UUID | None
    created_at: datetime
    updated_at: datetime


async def rows(session, query, page):
    from app.db.pagination import read_page

    items, total = await read_page(session, query, page)
    return {"items": items, "total": total}


async def log(session, user, row, action, before=None):
    await record(
        session,
        actor_user_id=user.id,
        actor_role=user.platform_role.value,
        action_type=action,
        entity_type=row.__tablename__,
        entity_id=row.id,
        event_id=row.event_id,
        summary=action.replace(".", " "),
        metadata={"before": before, "status": row.status},
    )


async def notify_payout(session, row):
    user = await session.get(User, row.organizer_user_id)
    for channel in (NotificationChannel.IN_APP, NotificationChannel.EMAIL):
        await enqueue(
            session,
            user_id=user.id,
            type=NotificationType.PAYOUT_STATUS,
            channel=channel,
            template_key=f"payout_status.{user.locale}",
            related_entity_type="simulated_payout",
            related_entity_id=str(row.id),
            payload={
                "status": row.status,
                "amount": row.amount,
                "event_id": str(row.event_id),
                "to_email": user.email,
            },
        )


@router.get("/events/{event_id}/payouts", response_model=Page[PayoutOut])
async def event_payouts(
    access: EventAccess = Depends(manager),
    session: AsyncSession = Depends(get_session),
    page: Pagination = Depends(pagination),
):
    return await rows(
        session,
        select(SimulatedPayout)
        .where(SimulatedPayout.event_id == access.event_id)
        .order_by(SimulatedPayout.created_at),
        page,
    )


@router.post("/events/{event_id}/payouts", response_model=PayoutOut)
async def request_payout(
    access: EventAccess = Depends(owner),
    session: AsyncSession = Depends(get_session),
):
    # Serialize duplicate requests and the snapshot against refunds/checkout.
    event = await get_event(session, access.event_id, lock=True)
    existing = await session.scalar(
        select(SimulatedPayout).where(SimulatedPayout.event_id == event.id)
    )
    if existing:
        return existing
    if event.ends_at > datetime.now(UTC) or event.status == "cancelled":
        raise AppError("PAYOUT_NOT_READY", "Payouts require a completed, uncancelled event.", 409)
    result = await analytics.summary(session, event.id, ReportFilters())
    amount = result["estimated_payout_amount"]
    if amount <= 0:
        raise AppError("PAYOUT_EMPTY", "There is no simulated payout balance.", 409)
    row = SimulatedPayout(
        event_id=event.id, organizer_user_id=access.user.id, amount=amount, status="requested"
    )
    session.add(row)
    await session.flush()
    await log(session, access.user, row, "payout.requested")
    await notify_payout(session, row)
    await session.commit()
    return row


@router.get("/admin/payouts", response_model=Page[PayoutOut])
async def payout_queue(
    status: Literal["requested", "processing", "paid", "failed"] | None = None,
    user: User = Depends(require_platform_admin),
    session: AsyncSession = Depends(get_session),
    page: Pagination = Depends(pagination),
):
    query = select(SimulatedPayout).order_by(SimulatedPayout.created_at.desc(), SimulatedPayout.id)
    return await rows(
        session, query.where(SimulatedPayout.status == status) if status else query, page
    )


@router.patch("/admin/payouts/{payout_id}", response_model=PayoutOut)
async def transition_payout(
    payout_id: uuid.UUID,
    data: PayoutUpdate,
    user: User = Depends(require_platform_admin),
    session: AsyncSession = Depends(get_session),
):
    initial = await session.get(SimulatedPayout, payout_id)
    if not initial:
        raise AppError("NOT_FOUND", "Payout not found.", 404)
    event = await get_event(session, initial.event_id, lock=True)
    row = await session.scalar(
        select(SimulatedPayout)
        .where(SimulatedPayout.id == payout_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if row.status == data.status:
        return row
    allowed = {
        "requested": {"processing"},
        "processing": {"paid", "failed"},
        "failed": {"processing"},
        "paid": set(),
    }
    if data.status not in allowed[row.status]:
        raise AppError("INVALID_PAYOUT_TRANSITION", "Invalid simulated payout transition.", 409)
    if data.status in ("processing", "paid"):
        balance = await analytics.summary(session, event.id, ReportFilters())
        if event.status == "cancelled" or balance["estimated_payout_amount"] < row.amount:
            raise AppError(
                "PAYOUT_BALANCE_CHANGED",
                "Refunds changed the payout balance; mark this request failed.",
                409,
            )
    before = row.status
    row.status, row.note, row.updated_at = data.status, data.note, datetime.now(UTC)
    await log(session, user, row, "payout.status_changed", before)
    await notify_payout(session, row)
    await session.commit()
    return row


@router.post("/events/{event_id}/reports", response_model=ReportOut, status_code=201)
async def report_event(
    event_id: uuid.UUID,
    data: ReportCreate,
    user: User = Depends(require_verified),
    session: AsyncSession = Depends(get_session),
):
    await visible_event(session, event_id, user)
    # One active report per reporter/event avoids accidental duplicate submission.
    await session.execute(select(User.id).where(User.id == user.id).with_for_update())
    row = await session.scalar(
        select(EventReport).where(
            EventReport.event_id == event_id,
            EventReport.reporter_user_id == user.id,
            EventReport.status.in_(["open", "reviewing"]),
        )
    )
    if row:
        return row
    row = EventReport(
        event_id=event_id, reporter_user_id=user.id, reason=data.reason, status="open"
    )
    session.add(row)
    await session.flush()
    await log(session, user, row, "event_report.created")
    await session.commit()
    return row


@router.get("/admin/event-reports", response_model=Page[ReportOut])
async def report_queue(
    status: Literal["open", "reviewing", "resolved", "dismissed"] | None = None,
    user: User = Depends(require_platform_admin),
    session: AsyncSession = Depends(get_session),
    page: Pagination = Depends(pagination),
):
    query = select(EventReport).order_by(EventReport.created_at.desc(), EventReport.id)
    return await rows(session, query.where(EventReport.status == status) if status else query, page)


@router.patch("/admin/event-reports/{report_id}", response_model=ReportOut)
async def review_report(
    report_id: uuid.UUID,
    data: ReportUpdate,
    user: User = Depends(require_platform_admin),
    session: AsyncSession = Depends(get_session),
):
    row = await session.scalar(
        select(EventReport).where(EventReport.id == report_id).with_for_update()
    )
    if not row:
        raise AppError("NOT_FOUND", "Report not found.", 404)
    if row.status == data.status:
        return row
    if row.status in ("resolved", "dismissed") or (
        row.status == "reviewing" and data.status == "reviewing"
    ):
        raise AppError("REPORT_CLOSED", "This report is already closed.", 409)
    before = row.status
    row.status, row.resolution, row.reviewed_by, row.updated_at = (
        data.status,
        data.resolution,
        user.id,
        datetime.now(UTC),
    )
    await log(session, user, row, "event_report.reviewed", before)
    await session.commit()
    return row


class InventoryOut(BaseModel):
    ticket_type_id: uuid.UUID
    name: str
    capacity: int
    available: int
    reserved: int
    sold: int
    refunded: int
    cancelled: int
    checked_in: int


@router.get("/events/{event_id}/inventory", response_model=Page[InventoryOut])
async def inventory(
    access: EventAccess = Depends(manager),
    session: AsyncSession = Depends(get_session),
    page: Pagination = Depends(pagination),
):
    from sqlalchemy import text

    result = (
        (
            await session.execute(
                text("""
      SELECT t.id AS ticket_type_id, t.name, t.quantity_total AS capacity,
             t.quantity_total-t.quantity_reserved-t.quantity_sold AS available,
             t.quantity_reserved AS reserved, t.quantity_sold AS sold,
             count(k.id) FILTER(WHERE k.status='refunded') AS refunded,
             count(k.id) FILTER(WHERE k.status='cancelled') AS cancelled,
             count(k.id) FILTER(WHERE k.status='checked_in') AS checked_in
      FROM ticket_types t LEFT JOIN tickets k ON k.ticket_type_id=t.id
      WHERE t.event_id=:event_id GROUP BY t.id ORDER BY t.display_order,t.id
      LIMIT :limit OFFSET :offset
    """),
                {"event_id": access.event_id, "limit": page.limit, "offset": page.offset},
            )
        )
        .mappings()
        .all()
    )
    from sqlalchemy import func

    from app.modules.ticketing.models import TicketType

    total = await session.scalar(
        select(func.count()).select_from(TicketType).where(TicketType.event_id == access.event_id)
    )
    return {"items": result, "total": total}
