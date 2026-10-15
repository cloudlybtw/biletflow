from fastapi import APIRouter, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import EventAccess, require_event_role
from app.core.pagination import Page, Pagination, pagination
from app.core.reporting import EXPORT_LIMIT, ReportFilters, csv_response, report_filters
from app.db.session import get_session
from app.modules.analytics import service
from app.modules.analytics.schemas import (
    AttendanceOut,
    CampaignReportOut,
    DailySalesOut,
    PromoReportOut,
    SummaryOut,
    TicketTypeSalesOut,
)
from app.modules.users.models import StaffRole

router = APIRouter(prefix="/events/{event_id}/analytics", tags=["analytics"])
manager = require_event_role(StaffRole.CO_ORGANIZER, allow_platform_admin=True)


@router.get(
    "/summary",
    response_model=SummaryOut,
    summary="Current inventory and simulated sales for an order cohort",
)
async def summary(
    filters: ReportFilters = Depends(report_filters),
    access: EventAccess = Depends(manager),
    session: AsyncSession = Depends(get_session),
):
    return await service.summary(session, access.event_id, filters)


@router.get(
    "/attendance",
    response_model=AttendanceOut,
    summary="Current attendance within the selected order cohort",
)
async def attendance(
    filters: ReportFilters = Depends(report_filters),
    access: EventAccess = Depends(manager),
    session: AsyncSession = Depends(get_session),
):
    return await service.attendance(session, access.event_id, filters)


def report_endpoint(kind):
    async def endpoint(
        filters: ReportFilters = Depends(report_filters),
        page: Pagination = Depends(pagination),
        access: EventAccess = Depends(manager),
        session: AsyncSession = Depends(get_session),
    ):
        items, total = await service.report(session, access.event_id, filters, kind, page)
        return {"items": items, "total": total}

    endpoint.__name__ = "analytics_" + kind.replace("-", "_")
    return endpoint


def export_endpoint(kind, model):
    async def endpoint(
        filters: ReportFilters = Depends(report_filters),
        access: EventAccess = Depends(manager),
        session: AsyncSession = Depends(get_session),
    ):
        if kind == "attendance":
            rows = [await service.attendance(session, access.event_id, filters)]
        elif kind == "summary":
            rows = [await service.summary(session, access.event_id, filters)]
        else:
            rows, total = await service.report(
                session, access.event_id, filters, kind, Pagination(EXPORT_LIMIT + 1, 0)
            )
        rows = [model.model_validate(row).model_dump() for row in rows]
        return csv_response(rows, list(model.model_fields), "event-" + kind)

    endpoint.__name__ = "export_" + kind.replace("-", "_")
    return endpoint


for kind, path, model in [
    ("daily", "/sales/daily", DailySalesOut),
    ("ticket-types", "/sales/ticket-types", TicketTypeSalesOut),
    ("campaigns", "/campaigns", CampaignReportOut),
    ("promo-codes", "/promo-codes", PromoReportOut),
]:
    router.add_api_route(
        path,
        report_endpoint(kind),
        response_model=Page[model],
        methods=["GET"],
        summary=f"Simulated sales report: {kind}",
    )

for kind, path, model in [
    ("summary", "/summary", SummaryOut),
    ("attendance", "/attendance", AttendanceOut),
    ("daily", "/sales/daily", DailySalesOut),
    ("ticket-types", "/sales/ticket-types", TicketTypeSalesOut),
    ("campaigns", "/campaigns", CampaignReportOut),
    ("promo-codes", "/promo-codes", PromoReportOut),
]:
    router.add_api_route(
        path + ".csv",
        export_endpoint(kind, model),
        response_class=Response,
        responses={200: {"content": {"text/csv": {}}}},
        methods=["GET"],
        summary=f"Export {kind} as UTF-8 CSV",
    )
