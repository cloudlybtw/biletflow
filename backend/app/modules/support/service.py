import secrets
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import (
    FORBIDDEN,
    NOT_FOUND,
    SUPPORT_ASSIGNEE_INVALID,
    SUPPORT_CONTEXT_INVALID,
    AppError,
)
from app.core.pagination import Pagination
from app.db.pagination import read_page
from app.modules.events.models import Event
from app.modules.events.service import visible_event
from app.modules.history import service as history
from app.modules.notifications import service as notifications
from app.modules.notifications.models import NotificationChannel, NotificationType
from app.modules.orders.models import Order, OrderItem
from app.modules.organizers.models import OrganizerProfile
from app.modules.support.models import CaseStatus, CaseType, SenderRole, SupportCase, SupportMessage
from app.modules.support.schemas import CaseCreate, CaseOut, MessageCreate, MessageOut
from app.modules.tickets.models import Ticket
from app.modules.users import service as users
from app.modules.users.models import PlatformRole, StaffAssignment, StaffRole, User, UserStatus

SUPPORT_ROLES = (StaffRole.CO_ORGANIZER, StaffRole.SUPPORT_AGENT)


@dataclass(frozen=True)
class CaseAccess:
    user: User
    case: SupportCase
    is_requester: bool
    can_manage: bool
    can_read_internal: bool


async def staff_for_case(session: AsyncSession, case: SupportCase, user: User) -> bool:
    if case.case_type == CaseType.ORGANIZER:
        return user.platform_role == PlatformRole.PLATFORM_ADMIN
    if case.event_id is None:
        return False
    relation = await users.get_event_relation(session, case.event_id, user.id)
    return bool(
        relation and (relation.is_owner or relation.staff_roles.intersection(SUPPORT_ROLES))
    )


async def access_case(
    session: AsyncSession, user: User, case_id: uuid.UUID, *, lock=False
) -> CaseAccess:
    case = await session.get(SupportCase, case_id)
    if case is None:
        raise AppError(NOT_FOUND, "Support case not found.", 404)
    if lock:
        # Match event administration's lock order and re-check revoked assignments
        # after the event lock, then serialize case changes and message timestamps.
        if case.case_type == CaseType.ATTENDEE and case.event_id:
            await session.execute(
                select(Event.id).where(Event.id == case.event_id).with_for_update(key_share=True)
            )
        case = await session.scalar(
            select(SupportCase)
            .where(SupportCase.id == case_id)
            .with_for_update(key_share=True)
            .execution_options(populate_existing=True)
        )
    requester = case.opened_by_user_id == user.id
    staff = await staff_for_case(session, case, user)
    admin = user.platform_role == PlatformRole.PLATFORM_ADMIN
    if not (requester or staff or admin):
        raise AppError(NOT_FOUND, "Support case not found.", 404)
    return CaseAccess(user, case, requester, staff, staff or admin)


async def context_for_create(session: AsyncSession, user: User, data: CaseCreate):
    event_id, order_id, ticket_id = data.event_id, data.order_id, data.ticket_id
    if data.case_type == CaseType.ORGANIZER:
        profile = await session.scalar(
            select(OrganizerProfile).where(OrganizerProfile.user_id == user.id)
        )
        if profile is None:
            raise AppError(
                FORBIDDEN, "Organizer profile required for a platform support case.", 403
            )
        if event_id is not None:
            event = await session.scalar(
                select(Event.id).where(
                    Event.id == event_id,
                    Event.organizer_profile_id == profile.id,
                    Event.deleted_at.is_(None),
                )
            )
            if event is None:
                raise AppError(NOT_FOUND, "Event not found.", 404)
        return event_id, None, None
    if ticket_id:
        row = (
            await session.execute(
                select(Order.id, Order.event_id)
                .join(OrderItem, OrderItem.order_id == Order.id)
                .join(Ticket, Ticket.order_item_id == OrderItem.id)
                .where(Ticket.id == ticket_id, Order.buyer_user_id == user.id)
            )
        ).one_or_none()
        if row is None:
            raise AppError(NOT_FOUND, "Ticket not found.", 404)
        if (order_id and order_id != row.id) or (event_id and event_id != row.event_id):
            raise AppError(
                SUPPORT_CONTEXT_INVALID, "Ticket, order and event context must match.", 400
            )
        order_id, event_id = row.id, row.event_id
    elif order_id:
        order = await session.scalar(
            select(Order).where(Order.id == order_id, Order.buyer_user_id == user.id)
        )
        if order is None:
            raise AppError(NOT_FOUND, "Order not found.", 404)
        if event_id and event_id != order.event_id:
            raise AppError(SUPPORT_CONTEXT_INVALID, "Order and event context must match.", 400)
        event_id = order.event_id
    else:
        await visible_event(session, event_id, user)
    return event_id, order_id, ticket_id


async def staff_ids(session: AsyncSession, case: SupportCase) -> set[uuid.UUID]:
    if case.case_type == CaseType.ORGANIZER:
        query = select(User.id).where(
            User.platform_role == PlatformRole.PLATFORM_ADMIN, User.status == UserStatus.ACTIVE
        )
    else:
        relation = (
            select(OrganizerProfile.user_id)
            .join(Event, Event.organizer_profile_id == OrganizerProfile.id)
            .where(Event.id == case.event_id, Event.deleted_at.is_(None))
        )
        assignments = (
            select(StaffAssignment.user_id)
            .join(Event, Event.id == StaffAssignment.event_id)
            .where(
                StaffAssignment.event_id == case.event_id,
                Event.deleted_at.is_(None),
                StaffAssignment.revoked_at.is_(None),
                StaffAssignment.role.in_(SUPPORT_ROLES),
            )
        )
        query = select(User.id).where(
            User.status == UserStatus.ACTIVE, (User.id.in_(relation) | User.id.in_(assignments))
        )
    return set((await session.scalars(query)).all())


async def responders(session: AsyncSession, case: SupportCase) -> set[uuid.UUID]:
    eligible = await staff_ids(session, case)
    return {case.assigned_to_user_id} if case.assigned_to_user_id in eligible else eligible


async def notify(
    session: AsyncSession, access: CaseAccess, kind: NotificationType, recipients: set[uuid.UUID]
):
    case = access.case
    for recipient in sorted(recipients - {access.user.id}):
        user = await session.get(User, recipient)
        if user is None or user.status != UserStatus.ACTIVE:
            continue
        await notifications.enqueue(
            session,
            user_id=recipient,
            type=kind,
            channel=NotificationChannel.IN_APP,
            template_key=f"{kind.value}.{user.locale}",
            related_entity_type="support_case",
            related_entity_id=str(case.id),
            payload={
                "case_id": str(case.id),
                "case_number": case.case_number,
                "status": case.status.value,
            },
        )


async def audit(session: AsyncSession, access: CaseAccess, action: str, metadata: dict):
    await history.record(
        session,
        actor_user_id=access.user.id,
        actor_role="requester" if access.is_requester else "support_staff",
        action_type=action,
        entity_type="support_cases",
        entity_id=access.case.id,
        event_id=access.case.event_id,
        summary=action.replace(".", " "),
        metadata=metadata,
    )


async def append_message(
    session: AsyncSession, access: CaseAccess, data: MessageCreate
) -> SupportMessage:
    if not (access.is_requester or access.can_manage) or (
        data.is_internal_note and not access.can_manage
    ):
        raise AppError(FORBIDDEN, "Support staff access required for this action.", 403)
    case = access.case
    now = datetime.now(UTC)
    latest = await session.scalar(
        select(func.max(SupportMessage.created_at)).where(SupportMessage.case_id == case.id)
    )
    if latest is not None:
        now = max(now, latest + timedelta(microseconds=1))
    message = SupportMessage(
        case_id=case.id,
        sender_user_id=access.user.id,
        sender_role=SenderRole.REQUESTER
        if access.is_requester and not data.is_internal_note
        else SenderRole.STAFF,
        body=data.body,
        is_internal_note=data.is_internal_note,
        created_at=now,
    )
    session.add(message)
    # Internal notes do not change requester-visible activity timestamps.
    if not data.is_internal_note:
        case.last_message_at = now
    await session.flush()
    await audit(
        session,
        access,
        "support.message_added",
        {"message_id": str(message.id), "is_internal_note": data.is_internal_note},
    )
    if not data.is_internal_note:
        recipients = (
            await responders(session, case)
            if message.sender_role == SenderRole.REQUESTER
            else {case.opened_by_user_id}
        )
        await notify(session, access, NotificationType.SUPPORT_NEW_MESSAGE, recipients)
    return message


async def create(session: AsyncSession, user: User, data: CaseCreate) -> CaseOut:
    event_id, order_id, ticket_id = await context_for_create(session, user, data)
    case = SupportCase(
        case_number="BFS-" + secrets.token_hex(8).upper(),
        case_type=data.case_type,
        category=data.category,
        subject=data.subject,
        opened_by_user_id=user.id,
        event_id=event_id,
        order_id=order_id,
        ticket_id=ticket_id,
    )
    session.add(case)
    await session.flush()
    access = CaseAccess(user, case, True, False, False)
    await append_message(session, access, MessageCreate(body=data.body))
    await audit(
        session,
        access,
        "support.opened",
        {"case_number": case.case_number, "case_type": case.case_type.value},
    )
    result = CaseOut.model_validate(case)
    await session.commit()
    return result


async def list_cases(session: AsyncSession, query, page: Pagination, status: CaseStatus | None):
    if status is not None:
        query = query.where(SupportCase.status == status)
    rows, total = await read_page(
        session, query.order_by(SupportCase.updated_at.desc(), SupportCase.id), page
    )
    return [CaseOut.model_validate(row) for row in rows], total


async def my_cases(session: AsyncSession, user: User, page: Pagination, status: CaseStatus | None):
    return await list_cases(
        session, select(SupportCase).where(SupportCase.opened_by_user_id == user.id), page, status
    )


async def event_cases(
    session: AsyncSession, event_id: uuid.UUID, page: Pagination, status: CaseStatus | None
):
    return await list_cases(
        session,
        select(SupportCase).where(
            SupportCase.event_id == event_id, SupportCase.case_type == CaseType.ATTENDEE
        ),
        page,
        status,
    )


async def admin_cases(
    session: AsyncSession,
    page: Pagination,
    status: CaseStatus | None,
    case_type: CaseType | None,
    *,
    event_id=None,
    order_id=None,
    category=None,
):
    query = select(SupportCase)
    if case_type is not None:
        query = query.where(SupportCase.case_type == case_type)
    for column, value in (
        (SupportCase.event_id, event_id),
        (SupportCase.order_id, order_id),
        (SupportCase.category, category),
    ):
        if value is not None:
            query = query.where(column == value)
    return await list_cases(session, query, page, status)


async def messages(
    session: AsyncSession, access: CaseAccess, page: Pagination, since: datetime | None
):
    query = select(SupportMessage).where(SupportMessage.case_id == access.case.id)
    if not access.can_read_internal:
        query = query.where(~SupportMessage.is_internal_note)
    if since is not None:
        query = query.where(SupportMessage.created_at >= since)
    rows, total = await read_page(
        session, query.order_by(SupportMessage.created_at, SupportMessage.id), page
    )
    return [MessageOut.model_validate(row) for row in rows], total


async def post_message(session: AsyncSession, access: CaseAccess, data: MessageCreate):
    access = await access_case(session, access.user, access.case.id, lock=True)
    message = await append_message(session, access, data)
    result = MessageOut.model_validate(message)
    await session.commit()
    return result


async def assign(session: AsyncSession, access: CaseAccess, user_id: uuid.UUID | None):
    access = await access_case(session, access.user, access.case.id, lock=True)
    if not access.can_manage:
        raise AppError(FORBIDDEN, "Support staff access required.", 403)
    if user_id is not None and user_id not in await staff_ids(session, access.case):
        raise AppError(
            SUPPORT_ASSIGNEE_INVALID, "Assignee must be active support staff for this case.", 400
        )
    case = access.case
    if case.assigned_to_user_id != user_id:
        before = case.assigned_to_user_id
        case.assigned_to_user_id = user_id
        await session.flush()
        await audit(
            session,
            access,
            "support.assigned",
            {"before": str(before) if before else None, "after": str(user_id) if user_id else None},
        )
        recipients = {case.opened_by_user_id}
        if user_id:
            recipients.add(user_id)
        if before and before in await staff_ids(session, case):
            recipients.add(before)
        await notify(session, access, NotificationType.SUPPORT_ASSIGNED, recipients)
    result = CaseOut.model_validate(case)
    await session.commit()
    return result


async def change_status(session: AsyncSession, access: CaseAccess, status: CaseStatus):
    access = await access_case(session, access.user, access.case.id, lock=True)
    if not access.can_manage:
        raise AppError(FORBIDDEN, "Support staff access required.", 403)
    case = access.case
    if case.status != status:
        before = case.status
        case.status = status
        case.resolved_at = datetime.now(UTC) if status == CaseStatus.RESOLVED else None
        await session.flush()
        await audit(
            session,
            access,
            "support.status_changed",
            {"before": before.value, "after": status.value},
        )
        await notify(
            session,
            access,
            NotificationType.SUPPORT_STATUS_CHANGED,
            {case.opened_by_user_id} | await responders(session, case),
        )
    result = CaseOut.model_validate(case)
    await session.commit()
    return result
