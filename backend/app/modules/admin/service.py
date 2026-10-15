from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.modules.activation import service as activation_service
from app.modules.activation.models import ActivationStatus
from app.modules.admin.schemas import EventModerationOut
from app.modules.events.models import Event, EventStatus, PaidSalesStatus
from app.modules.events.service import get_event
from app.modules.users.models import User


def output(event: Event) -> EventModerationOut:
    return EventModerationOut(
        event_id=event.id,
        status=event.status,
        paid_sales_status=event.paid_sales_status,
        is_suspended=event.is_suspended,
        suspended_at=event.suspended_at,
        suspended_by=event.suspended_by,
        suspension_reason=event.suspension_reason,
    )


async def moderate_event(
    session: AsyncSession, event_id, user: User, *, suspend: bool, reason=None
) -> EventModerationOut:
    event = await get_event(session, event_id, lock=True)
    if event.status == EventStatus.CANCELLED:
        raise AppError("EVENT_CANCELLED", "Cancelled events cannot change moderation status.", 409)
    if event.is_suspended != suspend:
        event.is_suspended = suspend
        event.suspended_at = datetime.now(UTC) if suspend else None
        event.suspended_by = user.id if suspend else None
        event.suspension_reason = reason if suspend else None
        await activation_service.audit(
            session,
            event,
            user,
            "event.suspended" if suspend else "event.unsuspended",
            metadata={"reason": reason} if suspend else {},
            admin=True,
        )
    await session.commit()
    return output(event)


async def moderate_paid_sales(
    session: AsyncSession, event_id, user: User, *, suspend: bool, reason=None
) -> EventModerationOut:
    event = await get_event(session, event_id, lock=True)
    if event.status == EventStatus.CANCELLED:
        raise AppError(
            "EVENT_CANCELLED", "Cancelled events cannot change paid-sales moderation.", 409
        )
    activation = await activation_service.get_activation(session, event)
    changed = (event.paid_sales_status == PaidSalesStatus.SUSPENDED) != suspend
    if changed:
        if suspend:
            event.paid_sales_status = PaidSalesStatus.SUSPENDED
            if activation:
                activation.status = ActivationStatus.SUSPENDED
                activation.suspended_at = datetime.now(UTC)
                activation.suspended_by = user.id
                activation.suspension_reason = reason
        else:
            if activation and activation.activated_at:
                # Restoration never bypasses the checklist or refunds/revokes the original fee.
                if event.ends_at <= datetime.now(UTC):
                    raise AppError("EVENT_ENDED", "This event has ended.", 409)
                await activation_service.verify_requirements(session, event, activation)
                activation.status = ActivationStatus.ACTIVE
                event.paid_sales_status = PaidSalesStatus.ACTIVE
            else:
                event.paid_sales_status = (
                    PaidSalesStatus.PENDING if activation else PaidSalesStatus.DISABLED
                )
                if activation:
                    activation.status = ActivationStatus.PENDING
            if activation:
                activation.suspended_at = None
                activation.suspended_by = None
                activation.suspension_reason = None
        await activation_service.audit(
            session,
            event,
            user,
            "paid_sales.suspended" if suspend else "paid_sales.unsuspended",
            entity=activation,
            metadata={"reason": reason} if suspend else {},
            admin=True,
        )
    await session.commit()
    return output(event)
