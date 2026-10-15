import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import EventAccess, require_event_role
from app.core.pagination import Page, Pagination, pagination
from app.core.reporting import ReportFilters, SearchQuery, date_filters, report_filters
from app.db.session import get_session
from app.modules.analytics.service import parameters
from app.modules.checkin.models import CheckInResult
from app.modules.history import reads
from app.modules.history.schemas import (
    HistoryOut,
    ManagedCheckInOut,
    ManagedOrderDetail,
    ManagedOrderOut,
    ManagedTicketOut,
)
from app.modules.orders.models import OrderStatus
from app.modules.refunds.models import RefundStatus
from app.modules.refunds.schemas import RefundOut
from app.modules.tickets.models import TicketStatus
from app.modules.users.models import StaffRole

router = APIRouter(prefix="/events/{event_id}", tags=["history"])
manager = require_event_role(StaffRole.CO_ORGANIZER, allow_platform_admin=True)
checkin_reader = require_event_role(
    StaffRole.CO_ORGANIZER, StaffRole.EVENT_ADMIN, allow_platform_admin=True
)


@router.get(
    "/history",
    response_model=Page[HistoryOut],
    summary="Read the immutable chronological event activity timeline",
)
async def timeline(
    action_type: str | None = Query(None, min_length=1, max_length=100),
    filters: ReportFilters = Depends(date_filters),
    page: Pagination = Depends(pagination),
    access: EventAccess = Depends(manager),
    session: AsyncSession = Depends(get_session),
):
    items, total = await reads.timeline(session, access.event_id, filters, page, action_type)
    return Page(items=items, total=total)


@router.get(
    "/orders",
    response_model=Page[ManagedOrderOut],
    summary="Organizer event orders including retained terminal history",
)
async def orders(
    status: OrderStatus | None = None,
    q: str | None = SearchQuery,
    filters: ReportFilters = Depends(report_filters),
    page: Pagination = Depends(pagination),
    access: EventAccess = Depends(manager),
    session: AsyncSession = Depends(get_session),
):
    await parameters(session, access.event_id, filters)
    items, total = await reads.orders(session, access.event_id, filters, page, status, q)
    return Page(items=items, total=total)


@router.get(
    "/orders/{order_id}",
    response_model=ManagedOrderDetail,
    summary="Read an event order without expiring or changing it",
)
async def order_detail(
    order_id: uuid.UUID,
    access: EventAccess = Depends(manager),
    session: AsyncSession = Depends(get_session),
):
    return await reads.order_detail(session, access.event_id, order_id)


@router.get(
    "/tickets",
    response_model=Page[ManagedTicketOut],
    summary="Organizer event tickets without admission tokens",
)
async def tickets(
    status: TicketStatus | None = None,
    filters: ReportFilters = Depends(report_filters),
    page: Pagination = Depends(pagination),
    access: EventAccess = Depends(manager),
    session: AsyncSession = Depends(get_session),
):
    await parameters(session, access.event_id, filters)
    items, total = await reads.tickets(session, access.event_id, filters, page, status)
    return Page(items=items, total=total)


@router.get(
    "/tickets/{ticket_id}",
    response_model=ManagedTicketOut,
    summary="Read a retained event ticket without its QR token",
)
async def ticket_detail(
    ticket_id: uuid.UUID,
    access: EventAccess = Depends(manager),
    session: AsyncSession = Depends(get_session),
):
    return await reads.ticket_detail(session, access.event_id, ticket_id, ReportFilters())


@router.get(
    "/refunds",
    response_model=Page[RefundOut],
    summary="Read retained simulated refunds for an event order cohort",
)
async def refunds(
    status: RefundStatus | None = None,
    filters: ReportFilters = Depends(report_filters),
    page: Pagination = Depends(pagination),
    access: EventAccess = Depends(manager),
    session: AsyncSession = Depends(get_session),
):
    await parameters(session, access.event_id, filters)
    items, total = await reads.refunds(session, access.event_id, filters, page, status)
    return Page(items=items, total=total)


@router.get(
    "/checkin/records",
    response_model=Page[ManagedCheckInOut],
    summary="Read event scan history without scanned tokens",
)
async def checkins(
    result: CheckInResult | None = None,
    filters: ReportFilters = Depends(report_filters),
    page: Pagination = Depends(pagination),
    access: EventAccess = Depends(checkin_reader),
    session: AsyncSession = Depends(get_session),
):
    await parameters(session, access.event_id, filters)
    items, total = await reads.checkins(session, access.event_id, filters, page, result)
    return Page(items=items, total=total)
