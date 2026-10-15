"""Platform-only operational reads and transactional account/settings changes."""

from datetime import UTC, datetime

from sqlalchemy import Text, or_, select, update

from app.core.errors import (
    ADMIN_SELF_SUSPENSION,
    NOT_FOUND,
    USER_STATE_INVALID,
    VALIDATION_ERROR,
    AppError,
)
from app.core.reporting import literal_pattern
from app.db.pagination import read_page
from app.db.settings import PlatformSetting
from app.modules.activation.models import ActivationStatus, PaidSalesActivation
from app.modules.admin.schemas import SettingOut
from app.modules.auth.models import UserToken, UserTokenPurpose
from app.modules.events.models import Event, EventStatus
from app.modules.events.service import event_out
from app.modules.history import reads
from app.modules.history import service as history
from app.modules.orders.models import Order, OrderStatus
from app.modules.payments.models import Payment, PaymentStatus
from app.modules.refunds.models import Refund, RefundStatus
from app.modules.users.models import User, UserStatus

RESOURCES = {
    "users": (User, UserStatus, (User.email.cast(Text), User.full_name)),
    "events": (Event, EventStatus, (Event.title, Event.slug)),
    "orders": (
        Order,
        OrderStatus,
        (Order.order_number, Order.buyer_email.cast(Text), Order.buyer_name),
    ),
    "payments": (Payment, PaymentStatus, (Payment.provider_payment_ref,)),
    "refunds": (Refund, RefundStatus, (Refund.provider_refund_ref,)),
    "activations": (PaidSalesActivation, ActivationStatus, ()),
}


async def search(
    session, resource, page, filters, q=None, status=None, event_id=None, purpose=None
):
    model, status_enum, fields = RESOURCES[resource]
    query = select(model)
    if status is not None:
        try:
            query = query.where(model.status == status_enum(status))
        except ValueError as exc:
            raise AppError(VALIDATION_ERROR, "Unknown status for this resource.", 422) from exc
    if purpose is not None:
        if resource != "payments":
            raise AppError(VALIDATION_ERROR, "purpose is a payment filter.", 422)
        query = query.where(Payment.purpose == purpose)
    if event_id:
        if resource == "events":
            query = query.where(Event.id == event_id)
        elif resource == "payments":
            query = (
                query.outerjoin(Order, Order.id == Payment.order_id)
                .outerjoin(PaidSalesActivation, PaidSalesActivation.id == Payment.activation_id)
                .where(or_(Order.event_id == event_id, PaidSalesActivation.event_id == event_id))
            )
        elif resource == "refunds":
            query = query.join(Order, Order.id == Refund.order_id).where(Order.event_id == event_id)
        elif resource == "users":
            raise AppError(VALIDATION_ERROR, "Users do not have an event filter.", 422)
        else:
            query = query.where(model.event_id == event_id)
    if q:
        terms = [column.ilike(literal_pattern(q), escape="\\") for column in fields]
        terms.append(model.id.cast(Text) == q.strip())
        if resource in {"payments", "refunds"}:
            matching_orders = select(Order.id).where(
                Order.order_number.ilike(literal_pattern(q), escape="\\")
            )
            terms.append(model.order_id.in_(matching_orders))
        query = query.where(or_(*terms))
    column = Order.placed_at if resource == "orders" else model.created_at
    query = reads.range_query(query, column, filters).order_by(column.desc().nulls_last(), model.id)
    rows, total = await read_page(session, query, page)
    return ([event_out(row) for row in rows] if resource == "events" else rows), total


async def detail(session, resource, resource_id):
    model = RESOURCES[resource][0]
    row = await session.get(model, resource_id)
    if row is None:
        raise AppError(NOT_FOUND, "Resource not found.", 404)
    if resource == "orders":
        return await reads.order_detail(session, row.event_id, row.id)
    return event_out(row) if resource == "events" else row


async def moderate_user(session, user_id, actor, *, suspend, reason=None):
    if suspend and user_id == actor.id:
        raise AppError(
            ADMIN_SELF_SUSPENSION, "Administrators cannot suspend their own account.", 409
        )
    target = await session.scalar(
        select(User)
        .where(User.id == user_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if target is None:
        raise AppError(NOT_FOUND, "User not found.", 404)
    if target.status == UserStatus.DELETED:
        raise AppError(USER_STATE_INVALID, "Deleted accounts cannot be restored or suspended.", 409)
    wanted = UserStatus.SUSPENDED if suspend else UserStatus.ACTIVE
    if target.status != wanted:
        target.status = wanted
        if suspend:
            await session.execute(
                update(UserToken)
                .where(
                    UserToken.user_id == target.id,
                    UserToken.purpose == UserTokenPurpose.REFRESH,
                    UserToken.used_at.is_(None),
                )
                .values(used_at=datetime.now(UTC))
            )
        await history.record(
            session,
            actor_user_id=actor.id,
            actor_role="platform_admin",
            action_type="user.suspended" if suspend else "user.unsuspended",
            entity_type="users",
            entity_id=target.id,
            summary="User suspended" if suspend else "User unsuspended",
            metadata={"reason": reason} if suspend else {},
        )
        await session.flush()
        await session.refresh(target)
    await session.commit()
    return target


async def settings(session, page):
    return await read_page(session, select(PlatformSetting).order_by(PlatformSetting.key), page)


async def update_settings(session, actor, data):
    changes = data.model_dump(exclude_unset=True)
    rows = list(
        (
            await session.scalars(
                select(PlatformSetting)
                .where(PlatformSetting.key.in_(changes))
                .order_by(PlatformSetting.key)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
        ).all()
    )
    if len(rows) != len(changes):
        raise AppError(NOT_FOUND, "A configured setting is missing.", 404)
    for row in rows:
        value = changes[row.key]
        if row.value != value:
            before = row.value
            row.value, row.updated_by = value, actor.id
            await history.record(
                session,
                actor_user_id=actor.id,
                actor_role="platform_admin",
                action_type="platform_setting.updated",
                entity_type="platform_settings",
                entity_id=row.key,
                summary="Platform setting updated",
                metadata={"before": before, "after": value},
            )
    await session.flush()
    for row in rows:
        await session.refresh(row)
    result = [SettingOut.model_validate(row) for row in rows]
    await session.commit()
    return result
