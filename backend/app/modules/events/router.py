import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Form, Query, Response, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import (
    EventAccess,
    current_user,
    optional_current_user,
    require_event_role,
    require_verified,
)
from app.core.errors import AppError
from app.core.pagination import Page, Pagination, pagination
from app.db.session import get_session
from app.modules.events import images, service
from app.modules.events.models import EventStatus
from app.modules.events.schemas import (
    CategoryOut,
    EventCreate,
    EventOut,
    EventUpdate,
    ImageOut,
    ImageUpdate,
    StaffCreate,
    StaffOut,
)
from app.modules.ticketing import service as ticket_service
from app.modules.ticketing.schemas import TicketTypeCreate, TicketTypeOut, TicketTypeUpdate
from app.modules.users.models import StaffRole, User

router = APIRouter(tags=["events"])
owner = require_event_role()
editor = require_event_role(StaffRole.CO_ORGANIZER)
reader = require_event_role(StaffRole.EVENT_ADMIN, StaffRole.CO_ORGANIZER, StaffRole.SUPPORT_AGENT)


@router.get("/event-categories", response_model=Page[CategoryOut])
async def categories(
    page: Pagination = Depends(pagination), session: AsyncSession = Depends(get_session)
):
    items, total = await service.list_categories(session, page)
    return Page(items=items, total=total)


@router.get("/events", response_model=Page[EventOut])
async def browse(
    page: Pagination = Depends(pagination),
    category_id: uuid.UUID | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    city: str | None = Query(None, max_length=200),
    q: str | None = Query(None, max_length=200),
    session: AsyncSession = Depends(get_session),
):
    for value in (date_from, date_to):
        if value is not None and value.tzinfo is None:
            raise AppError("VALIDATION_ERROR", "Date filters require a timezone offset.", 422)
    if date_from and date_to and date_to <= date_from:
        raise AppError("VALIDATION_ERROR", "date_to must be after date_from.", 422)
    events, total = await service.browse(
        session, page, category_id=category_id, date_from=date_from, date_to=date_to, city=city, q=q
    )
    return Page(items=[service.event_out(e) for e in events], total=total)


@router.post("/events", response_model=EventOut, status_code=201)
async def create(
    data: EventCreate,
    user: User = Depends(require_verified),
    session: AsyncSession = Depends(get_session),
):
    return service.event_out(await service.create(session, user, data))


@router.get("/events/my", response_model=Page[EventOut])
async def mine(
    page: Pagination = Depends(pagination),
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    events, total = await service.my_events(session, user, page)
    return Page(items=[service.event_out(e) for e in events], total=total)


@router.get("/events/assigned", response_model=Page[EventOut])
async def assigned(
    page: Pagination = Depends(pagination),
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    events, total = await service.my_events(session, user, page, assigned=True)
    return Page(items=[service.event_out(e) for e in events], total=total)


@router.get("/events/by-slug/{slug}", response_model=EventOut)
async def public_detail(slug: str, session: AsyncSession = Depends(get_session)):
    return service.event_out(await service.by_slug(session, slug))


@router.get(
    "/events/{event_id}",
    response_model=EventOut,
    summary="Organizer/staff event preview (including drafts)",
)
async def preview(
    event_id: uuid.UUID,
    access: EventAccess = Depends(reader),
    session: AsyncSession = Depends(get_session),
):
    return service.event_out(await service.get_event(session, access.event_id))


@router.patch("/events/{event_id}", response_model=EventOut)
async def edit(
    event_id: uuid.UUID,
    data: EventUpdate,
    access: EventAccess = Depends(editor),
    session: AsyncSession = Depends(get_session),
):
    return service.event_out(await service.update_event(session, access, data))


@router.delete(
    "/events/{event_id}",
    status_code=204,
    response_class=Response,
    summary="Soft-delete a draft and retain its audit trail",
)
async def delete(
    event_id: uuid.UUID,
    access: EventAccess = Depends(owner),
    session: AsyncSession = Depends(get_session),
):
    await service.delete_draft(session, access)
    return Response(status_code=204)


@router.post("/events/{event_id}/publish", response_model=EventOut)
async def publish(
    event_id: uuid.UUID,
    access: EventAccess = Depends(editor),
    session: AsyncSession = Depends(get_session),
):
    return service.event_out(await service.transition(session, access, EventStatus.PUBLISHED))


@router.post("/events/{event_id}/unpublish", response_model=EventOut)
async def unpublish(
    event_id: uuid.UUID,
    access: EventAccess = Depends(editor),
    session: AsyncSession = Depends(get_session),
):
    return service.event_out(await service.transition(session, access, EventStatus.UNPUBLISHED))


@router.post(
    "/events/{event_id}/cancel",
    response_model=EventOut,
    summary="Cancel an event and reverse its orders atomically",
    description="Owner only, including suspended events. Cancels free registrations, fully refunds completed paid orders (simulated), expires unpaid orders and releases their reservations. Queues buyer notifications and increments the calendar sequence once. Repeated cancellation returns the existing cancelled event.",
)
async def cancel(
    event_id: uuid.UUID,
    access: EventAccess = Depends(owner),
    session: AsyncSession = Depends(get_session),
):
    return service.event_out(await service.transition(session, access, EventStatus.CANCELLED))


@router.post("/events/{event_id}/duplicate", response_model=EventOut, status_code=201)
async def duplicate(
    event_id: uuid.UUID,
    access: EventAccess = Depends(owner),
    session: AsyncSession = Depends(get_session),
):
    return service.event_out(await service.duplicate(session, access))


@router.get("/events/{event_id}/ticket-types", response_model=Page[TicketTypeOut])
async def ticket_types(
    event_id: uuid.UUID,
    page: Pagination = Depends(pagination),
    user: User | None = Depends(optional_current_user),
    session: AsyncSession = Depends(get_session),
):
    items, total = await service.list_ticket_types(session, event_id, user, page)
    return Page(items=items, total=total)


@router.post("/events/{event_id}/ticket-types", response_model=TicketTypeOut, status_code=201)
async def create_ticket_type(
    event_id: uuid.UUID,
    data: TicketTypeCreate,
    access: EventAccess = Depends(editor),
    session: AsyncSession = Depends(get_session),
):
    return await ticket_service.save(session, access, data)


@router.patch("/events/{event_id}/ticket-types/{ticket_id}", response_model=TicketTypeOut)
async def update_ticket_type(
    event_id: uuid.UUID,
    ticket_id: uuid.UUID,
    data: TicketTypeUpdate,
    access: EventAccess = Depends(editor),
    session: AsyncSession = Depends(get_session),
):
    return await ticket_service.save(session, access, data, ticket_id)


@router.get("/events/{event_id}/staff", response_model=Page[StaffOut])
async def list_staff(
    event_id: uuid.UUID,
    page: Pagination = Depends(pagination),
    access: EventAccess = Depends(owner),
    session: AsyncSession = Depends(get_session),
):
    items, total = await service.list_staff(session, access, page)
    return Page(items=items, total=total)


@router.post("/events/{event_id}/staff", response_model=StaffOut, status_code=201)
async def assign_staff(
    event_id: uuid.UUID,
    data: StaffCreate,
    access: EventAccess = Depends(owner),
    session: AsyncSession = Depends(get_session),
):
    return await service.add_staff(session, access, data)


@router.delete("/events/{event_id}/staff/{assignment_id}", status_code=204, response_class=Response)
async def revoke_staff(
    event_id: uuid.UUID,
    assignment_id: uuid.UUID,
    access: EventAccess = Depends(owner),
    session: AsyncSession = Depends(get_session),
):
    await service.revoke_staff(session, access, assignment_id)
    return Response(status_code=204)


@router.get("/events/{event_id}/images", response_model=Page[ImageOut])
async def list_images(
    event_id: uuid.UUID,
    page: Pagination = Depends(pagination),
    user: User | None = Depends(optional_current_user),
    session: AsyncSession = Depends(get_session),
):
    items, total = await service.list_images(session, event_id, user, page)
    return Page(items=items, total=total)


@router.post("/events/{event_id}/images", response_model=ImageOut, status_code=201)
async def upload_image(
    event_id: uuid.UUID,
    file: UploadFile,
    is_cover: bool = Form(False),
    alt_text: str | None = Form(None, max_length=500),
    access: EventAccess = Depends(editor),
    session: AsyncSession = Depends(get_session),
):
    return await images.upload(session, access, file, is_cover, alt_text)


@router.patch("/events/{event_id}/images/{image_id}", response_model=ImageOut)
async def edit_image(
    event_id: uuid.UUID,
    image_id: uuid.UUID,
    data: ImageUpdate,
    access: EventAccess = Depends(editor),
    session: AsyncSession = Depends(get_session),
):
    return await images.edit(session, access, image_id, data)


@router.delete("/events/{event_id}/images/{image_id}", status_code=204, response_class=Response)
async def delete_image(
    event_id: uuid.UUID,
    image_id: uuid.UUID,
    access: EventAccess = Depends(editor),
    session: AsyncSession = Depends(get_session),
):
    await images.delete(session, access, image_id)
    return Response(status_code=204)


@router.get(
    "/events/{event_id}/images/{image_id}/file",
    response_class=FileResponse,
    responses={200: {"content": {"image/png": {}}}},
)
async def image_file(
    event_id: uuid.UUID,
    image_id: uuid.UUID,
    user: User | None = Depends(optional_current_user),
    session: AsyncSession = Depends(get_session),
):
    await service.visible_event(session, event_id, user)
    image = await images.get_image(session, event_id, image_id)
    path = images.image_path(image)
    if not path.is_file():
        raise AppError("NOT_FOUND", "Image file not found.", 404)
    return FileResponse(
        path,
        media_type="image/png",
        headers={"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"},
    )
