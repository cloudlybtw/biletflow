import uuid

from fastapi import APIRouter, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import require_platform_admin
from app.core.pagination import Page, Pagination, pagination
from app.core.reporting import (
    EXPORT_LIMIT,
    ReportFilters,
    SearchQuery,
    csv_response,
    date_filters,
)
from app.db.session import get_session
from app.modules.admin import operations
from app.modules.admin.schemas import (
    AdminActivationOut,
    AdminUserOut,
    SettingOut,
    SettingsUpdate,
    SuspensionRequest,
)
from app.modules.events.schemas import EventOut
from app.modules.history.schemas import ManagedOrderDetail, ManagedOrderOut
from app.modules.payments.models import PaymentPurpose
from app.modules.payments.schemas import PaymentOut
from app.modules.refunds.schemas import RefundOut
from app.modules.users.models import User

router = APIRouter(prefix="/admin", tags=["admin"])


def list_endpoint(resource, schema, export=False):
    status_enum = operations.RESOURCES[resource][1]

    async def endpoint(
        q: str | None = SearchQuery,
        status: status_enum | None = None,
        event_id: uuid.UUID | None = None,
        purpose: PaymentPurpose | None = None,
        filters: ReportFilters = Depends(date_filters),
        page: Pagination = Depends(pagination),
        user: User = Depends(require_platform_admin),
        session: AsyncSession = Depends(get_session),
    ):
        items, total = await operations.search(
            session,
            resource,
            Pagination(EXPORT_LIMIT + 1, 0) if export else page,
            filters,
            q,
            status,
            event_id,
            purpose,
        )
        if export:
            rows = [schema.model_validate(row).model_dump() for row in items]
            return csv_response(rows, list(schema.model_fields), "admin-" + resource)
        return {"items": items, "total": total}

    endpoint.__name__ = ("export_admin_" if export else "admin_search_") + resource
    return endpoint


def detail_endpoint(resource):
    async def endpoint(
        resource_id: uuid.UUID,
        user: User = Depends(require_platform_admin),
        session: AsyncSession = Depends(get_session),
    ):
        return await operations.detail(session, resource, resource_id)

    endpoint.__name__ = "admin_detail_" + resource
    return endpoint


for resource, schema, detail_schema in [
    ("users", AdminUserOut, AdminUserOut),
    ("events", EventOut, EventOut),
    ("orders", ManagedOrderOut, ManagedOrderDetail),
    ("payments", PaymentOut, PaymentOut),
    ("refunds", RefundOut, RefundOut),
    ("activations", AdminActivationOut, AdminActivationOut),
]:
    router.add_api_route(
        "/" + resource,
        list_endpoint(resource, schema),
        methods=["GET"],
        response_model=Page[schema],
        summary=f"Search platform {resource}",
    )
    # Export before UUID detail paths, so 'export.csv' is not parsed as a UUID.
    router.add_api_route(
        "/" + resource + "/export.csv",
        list_endpoint(resource, schema, True),
        methods=["GET"],
        response_class=Response,
        responses={200: {"content": {"text/csv": {}}}},
        summary=f"Export platform {resource} (maximum 10000 rows)",
    )
    router.add_api_route(
        "/" + resource + "/{resource_id}",
        detail_endpoint(resource),
        methods=["GET"],
        response_model=detail_schema,
        summary=f"Inspect a platform {resource} record",
    )


@router.post(
    "/users/{user_id}/suspend",
    response_model=AdminUserOut,
    summary="Suspend a user and revoke refresh sessions",
)
async def suspend_user(
    user_id: uuid.UUID,
    data: SuspensionRequest,
    user: User = Depends(require_platform_admin),
    session: AsyncSession = Depends(get_session),
):
    return await operations.moderate_user(session, user_id, user, suspend=True, reason=data.reason)


@router.post(
    "/users/{user_id}/unsuspend",
    response_model=AdminUserOut,
    summary="Restore a suspended user without restoring refresh sessions",
)
async def unsuspend_user(
    user_id: uuid.UUID,
    user: User = Depends(require_platform_admin),
    session: AsyncSession = Depends(get_session),
):
    return await operations.moderate_user(session, user_id, user, suspend=False)


@router.get(
    "/settings", response_model=Page[SettingOut], summary="Inspect configured platform settings"
)
async def settings(
    page: Pagination = Depends(pagination),
    user: User = Depends(require_platform_admin),
    session: AsyncSession = Depends(get_session),
):
    items, total = await operations.settings(session, page)
    return {"items": items, "total": total}


@router.patch(
    "/settings",
    response_model=Page[SettingOut],
    summary="Atomically update supported fees and hold durations",
)
async def update_settings(
    data: SettingsUpdate,
    user: User = Depends(require_platform_admin),
    session: AsyncSession = Depends(get_session),
):
    items = await operations.update_settings(session, user, data)
    return {"items": items, "total": len(items)}
