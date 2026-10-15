import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import EventAccess, require_event_role
from app.db.session import get_session
from app.modules.refunds import service
from app.modules.refunds.schemas import CancellationOut, RefundOut, ReversalIn
from app.modules.users.models import StaffRole

router = APIRouter(tags=["refunds"])
manage = require_event_role(StaffRole.CO_ORGANIZER)


@router.post(
    "/events/{event_id}/orders/{order_id}/cancel",
    response_model=CancellationOut,
    summary="Cancel a completed free registration",
    description="Owner or active co-organizer only. Invalidates all order tickets and returns inventory atomically. Repeated requests return 409.",
)
async def cancel_free(
    event_id: uuid.UUID,
    order_id: uuid.UUID,
    data: ReversalIn,
    access: EventAccess = Depends(manage),
    session: AsyncSession = Depends(get_session),
):
    return await service.cancel_free(session, access, order_id, data)


@router.post(
    "/events/{event_id}/orders/{order_id}/refunds",
    response_model=RefundOut,
    status_code=201,
    summary="Fully refund a completed paid order (simulated)",
    description="Owner or active co-organizer only. Refunds the captured total including fees, invalidates tickets and returns inventory in one transaction. Repeated requests return 409. No real money moves.",
)
async def refund_paid(
    event_id: uuid.UUID,
    order_id: uuid.UUID,
    data: ReversalIn,
    access: EventAccess = Depends(manage),
    session: AsyncSession = Depends(get_session),
):
    return await service.refund_paid(session, access, order_id, data)
