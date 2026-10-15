import re
import secrets
import uuid
from datetime import UTC, datetime

from fastapi import status
from fastapi.encoders import jsonable_encoder
from pydantic import ValidationError
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import EventAccess
from app.core.errors import NOT_FOUND, VALIDATION_ERROR, AppError
from app.core.pagination import Pagination
from app.db.pagination import read_page
from app.modules.events import cancellation
from app.modules.events.models import (
    Event,
    EventCategory,
    EventImage,
    EventStatus,
    EventVisibility,
    PaidSalesStatus,
)
from app.modules.events.schemas import EventCreate, EventFields, EventOut, EventUpdate, StaffCreate
from app.modules.history import service as history
from app.modules.notifications import service as notifications
from app.modules.notifications.models import NotificationChannel, NotificationType
from app.modules.orders.models import Order, OrderStatus
from app.modules.organizers import service as organizers
from app.modules.ticketing.models import TicketType
from app.modules.ticketing.schemas import TicketTypeCreate
from app.modules.users import service as users_service
from app.modules.users.models import StaffAssignment, StaffRole, User, UserStatus
from app.modules.venues.models import Venue


def not_found() -> AppError:
    return AppError(NOT_FOUND, "Event not found.", status.HTTP_404_NOT_FOUND)


async def list_categories(session: AsyncSession, page: Pagination):
    return await read_page(
        session,
        select(EventCategory).order_by(EventCategory.display_order, EventCategory.slug),
        page,
    )


async def visible_event(session: AsyncSession, event_id: uuid.UUID, user: User | None):
    event = await get_event(session, event_id)
    relation = await users_service.get_event_relation(session, event_id, user.id) if user else None
    privileged = bool(relation and (relation.is_owner or relation.staff_roles))
    if (
        not (
            not event.is_suspended
            and event.status == EventStatus.PUBLISHED
            and event.visibility != EventVisibility.PRIVATE
        )
        and not privileged
    ):
        raise not_found()
    return event, privileged


async def list_ticket_types(
    session: AsyncSession, event_id: uuid.UUID, user: User | None, page: Pagination
):
    _, privileged = await visible_event(session, event_id, user)
    query = select(TicketType).where(TicketType.event_id == event_id)
    if not privileged:
        query = query.where(~TicketType.is_hidden)
    return await read_page(session, query.order_by(TicketType.display_order, TicketType.id), page)


async def list_staff(session: AsyncSession, access: EventAccess, page: Pagination):
    return await read_page(
        session,
        select(StaffAssignment)
        .where(StaffAssignment.event_id == access.event_id)
        .order_by(StaffAssignment.created_at, StaffAssignment.id),
        page,
    )


async def list_images(
    session: AsyncSession, event_id: uuid.UUID, user: User | None, page: Pagination
):
    await visible_event(session, event_id, user)
    return await read_page(
        session,
        select(EventImage)
        .where(EventImage.event_id == event_id)
        .order_by(EventImage.sort_order, EventImage.id),
        page,
    )


def slug_for(title: str) -> str:
    base = re.sub(r"[^\w]+", "-", title.lower(), flags=re.UNICODE).strip("-")[:100] or "event"
    return f"{base}-{secrets.token_hex(6)}"


def event_out(event: Event) -> EventOut:
    now = datetime.now(UTC)
    classification = (
        "Cancelled"
        if event.status == EventStatus.CANCELLED
        else "Completed"
        if event.ends_at <= now
        else "Active"
        if event.starts_at <= now
        else "Upcoming"
    )
    return EventOut.model_validate(event).model_copy(update={"classification": classification})


async def audit(session: AsyncSession, access: EventAccess, action: str, entity, changes=None):
    await history.record(
        session,
        actor_user_id=access.user.id,
        actor_role=access.actor_role,
        action_type=action,
        entity_type=entity.__tablename__,
        entity_id=entity.id,
        event_id=access.event_id,
        summary=action.replace(".", " "),
        metadata=jsonable_encoder(changes or {}),
    )


async def get_event(session: AsyncSession, event_id: uuid.UUID, *, lock=False) -> Event:
    query = select(Event).where(Event.id == event_id, Event.deleted_at.is_(None))
    if lock:
        # Serialize event changes while allowing FK checks from ticket scans
        # which may already own a ticket needed by a cancellation cascade.
        query = query.with_for_update(key_share=True).execution_options(populate_existing=True)
    event = await session.scalar(query)
    if event is None:
        raise not_found()
    return event


def editable(event: Event) -> None:
    if event.is_suspended:
        raise AppError("EVENT_SUSPENDED", "This event is suspended.", 409)
    if event.status == EventStatus.CANCELLED:
        raise AppError("EVENT_CANCELLED", "Cancelled events cannot be modified.", 409)


async def validate_references(session: AsyncSession, data: EventFields) -> None:
    for identifier, model, label in [
        (data.venue_id, Venue, "Venue"),
        (data.category_id, EventCategory, "Category"),
    ]:
        if identifier is not None and await session.get(model, identifier) is None:
            raise AppError(VALIDATION_ERROR, f"{label} does not exist.", 422)


async def create(session: AsyncSession, user: User, data: EventCreate) -> Event:
    profile = await organizers.get_profile(session, user)
    await validate_references(session, data)
    event = Event(**data.model_dump(), organizer_profile_id=profile.id, slug=slug_for(data.title))
    session.add(event)
    await session.flush()
    access = EventAccess(user, event.id, True, frozenset(), False)
    await audit(session, access, "event.created", event)
    await session.commit()
    return event


async def update_event(session: AsyncSession, access: EventAccess, data: EventUpdate) -> Event:
    event = await get_event(session, access.event_id, lock=True)
    editable(event)
    changes = data.model_dump(exclude_unset=True)
    try:
        merged = EventFields.model_validate(
            {**EventFields.model_validate(event, from_attributes=True).model_dump(), **changes}
        )
    except ValidationError as exc:
        raise AppError(
            VALIDATION_ERROR,
            "Invalid event fields.",
            422,
            {"errors": jsonable_encoder(exc.errors())},
        ) from exc
    await validate_references(session, merged)
    if merged.capacity is not None:
        allocated = await session.scalar(
            select(func.coalesce(func.sum(TicketType.quantity_total), 0)).where(
                TicketType.event_id == event.id
            )
        )
        if merged.capacity < allocated:
            raise AppError(
                "CAPACITY_BELOW_INVENTORY",
                "Capacity cannot be below allocated ticket inventory.",
                409,
            )
    if event.venue_id != merged.venue_id or event.seating_mode != merged.seating_mode:
        sold = await session.scalar(
            select(
                func.coalesce(func.sum(TicketType.quantity_sold + TicketType.quantity_reserved), 0)
            ).where(TicketType.event_id == event.id)
        )
        if sold:
            raise AppError(
                "EVENT_HAS_RESERVATIONS", "Seating cannot change after reservations or sales.", 409
            )
    before = {key: getattr(event, key) for key in changes}
    for key in changes:
        setattr(event, key, getattr(merged, key))
    await audit(session, access, "event.updated", event, {"before": before, "after": changes})
    changed_fields = [key for key in changes if before[key] != getattr(merged, key)]
    if changed_fields:
        buyers = (
            await session.scalars(
                select(User)
                .join(Order, Order.buyer_user_id == User.id)
                .where(
                    Order.event_id == event.id,
                    Order.status.in_(
                        (OrderStatus.COMPLETED, OrderStatus.PENDING, OrderStatus.AWAITING_PAYMENT)
                    ),
                    User.status == UserStatus.ACTIVE,
                )
                .distinct()
            )
        ).all()
        for buyer in buyers:
            await notifications.enqueue(
                session,
                user_id=buyer.id,
                type=NotificationType.EVENT_UPDATE,
                channel=NotificationChannel.EMAIL,
                template_key=f"event_update.{buyer.locale}",
                related_entity_type="event",
                related_entity_id=str(event.id),
                payload={
                    "event_title": event.title,
                    "event_id": str(event.id),
                    "status": event.status.value,
                    "changed_fields": changed_fields,
                    "to_email": buyer.email,
                },
            )
    await session.commit()
    return event


async def transition(session: AsyncSession, access: EventAccess, target: EventStatus) -> Event:
    event = await get_event(session, access.event_id, lock=True)
    if target == EventStatus.CANCELLED and event.status == EventStatus.CANCELLED:
        await session.commit()
        return event
    if target != EventStatus.CANCELLED:
        editable(event)
    allowed = {
        EventStatus.PUBLISHED: {EventStatus.DRAFT, EventStatus.UNPUBLISHED},
        EventStatus.UNPUBLISHED: {EventStatus.PUBLISHED},
        EventStatus.CANCELLED: {EventStatus.DRAFT, EventStatus.PUBLISHED, EventStatus.UNPUBLISHED},
    }
    if event.status not in allowed.get(target, set()):
        raise AppError(
            "INVALID_EVENT_TRANSITION", "This event status transition is not allowed.", 409
        )
    if target == EventStatus.PUBLISHED:
        if event.ends_at <= datetime.now(UTC):
            raise AppError("EVENT_ENDED", "An ended event cannot be published.", 409)
        count = await session.scalar(
            select(func.count())
            .select_from(TicketType)
            .where(
                TicketType.event_id == event.id,
                ~TicketType.is_hidden,
                TicketType.quantity_total > 0,
            )
        )
        if not count:
            raise AppError(
                "EVENT_HAS_NO_TICKETS", "Add a visible ticket type before publishing.", 409
            )
        event.published_at = datetime.now(UTC)
    changes = None
    if target == EventStatus.CANCELLED:
        event.cancelled_at = datetime.now(UTC)
        event.ics_sequence += 1
        event.paid_sales_status = PaidSalesStatus.DISABLED
        event.status = target
        changes = await cancellation.cascade_locked(session, access, event)
    event.status = target
    await audit(session, access, f"event.{target.value}", event, changes)
    await session.commit()
    return event


async def delete_draft(session: AsyncSession, access: EventAccess) -> None:
    event = await get_event(session, access.event_id, lock=True)
    if event.status != EventStatus.DRAFT:
        raise AppError("EVENT_NOT_DRAFT", "Only draft events can be deleted.", 409)
    event.deleted_at = datetime.now(UTC)
    await audit(session, access, "event.deleted", event)
    await session.commit()


async def paged(session: AsyncSession, query, page: Pagination):
    total = await session.scalar(select(func.count()).select_from(query.order_by(None).subquery()))
    events = await session.scalars(
        query.order_by(Event.starts_at, Event.id).limit(page.limit).offset(page.offset)
    )
    return list(events.all()), total or 0


async def browse(
    session: AsyncSession,
    page: Pagination,
    *,
    category_id=None,
    date_from=None,
    date_to=None,
    city=None,
    q=None,
):
    query = select(Event).where(
        Event.deleted_at.is_(None),
        ~Event.is_suspended,
        Event.status == EventStatus.PUBLISHED,
        Event.visibility == EventVisibility.PUBLIC,
    )
    if category_id:
        query = query.where(Event.category_id == category_id)
    if date_from:
        query = query.where(Event.starts_at >= date_from)
    if date_to:
        query = query.where(Event.starts_at < date_to)
    if city:
        query = query.join(Venue, Venue.id == Event.venue_id).where(
            func.lower(Venue.city) == city.lower()
        )
    if q:
        # Escape SQL wildcard characters so user text remains a literal substring.
        pattern = "%" + q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
        query = query.where(
            or_(
                Event.title.ilike(pattern, escape="\\"),
                Event.description.ilike(pattern, escape="\\"),
            )
        )
    return await paged(session, query, page)


async def by_slug(session: AsyncSession, slug: str) -> Event:
    event = await session.scalar(
        select(Event).where(
            Event.slug == slug,
            Event.deleted_at.is_(None),
            ~Event.is_suspended,
            Event.status == EventStatus.PUBLISHED,
            Event.visibility != EventVisibility.PRIVATE,
        )
    )
    if event is None:
        raise not_found()
    return event


async def my_events(session: AsyncSession, user: User, page: Pagination, *, assigned=False):
    if assigned:
        query = select(Event).where(
            Event.id.in_(
                select(StaffAssignment.event_id).where(
                    StaffAssignment.user_id == user.id,
                    StaffAssignment.role == StaffRole.EVENT_ADMIN,
                    StaffAssignment.revoked_at.is_(None),
                )
            )
        )
    else:
        profile = await organizers.get_profile(session, user)
        query = select(Event).where(Event.organizer_profile_id == profile.id)
    return await paged(session, query.where(Event.deleted_at.is_(None)), page)


async def duplicate(session: AsyncSession, access: EventAccess) -> Event:
    original = await get_event(session, access.event_id, lock=True)
    data = EventFields.model_validate(original, from_attributes=True).model_dump()
    data["title"] = f"{original.title[:193]} (copy)"
    copy = Event(
        **data, organizer_profile_id=original.organizer_profile_id, slug=slug_for(data["title"])
    )
    session.add(copy)
    await session.flush()
    types = await session.scalars(select(TicketType).where(TicketType.event_id == original.id))
    for ticket in types:
        session.add(
            TicketType(
                **TicketTypeCreate.model_validate(ticket, from_attributes=True).model_dump(),
                event_id=copy.id,
            )
        )
    await audit(
        session,
        EventAccess(access.user, copy.id, True, frozenset(), False),
        "event.duplicated",
        copy,
        {"source_event_id": original.id},
    )
    await session.commit()
    return copy


async def add_staff(
    session: AsyncSession, access: EventAccess, data: StaffCreate
) -> StaffAssignment:
    event = await get_event(session, access.event_id, lock=True)
    editable(event)
    user = await session.scalar(
        select(User).where(User.email == str(data.email), User.status == UserStatus.ACTIVE)
    )
    if user is None:
        raise AppError(NOT_FOUND, "Active user not found.", 404)
    assignment = StaffAssignment(
        event_id=event.id, user_id=user.id, role=data.role, assigned_by=access.user.id
    )
    try:
        session.add(assignment)
        await session.flush()
    except IntegrityError as exc:
        await session.rollback()
        raise AppError("STAFF_ALREADY_ASSIGNED", "This user already has this role.", 409) from exc
    await audit(
        session, access, "staff.assigned", assignment, {"role": data.role, "user_id": user.id}
    )
    await session.commit()
    return assignment


async def revoke_staff(
    session: AsyncSession, access: EventAccess, assignment_id: uuid.UUID
) -> None:
    await get_event(session, access.event_id, lock=True)
    assignment = await session.scalar(
        select(StaffAssignment).where(
            StaffAssignment.id == assignment_id, StaffAssignment.event_id == access.event_id
        )
    )
    if assignment is None:
        raise AppError(NOT_FOUND, "Staff assignment not found.", 404)
    if assignment.revoked_at is None:
        assignment.revoked_at = datetime.now(UTC)
        await audit(session, access, "staff.revoked", assignment)
    await session.commit()
