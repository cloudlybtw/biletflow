import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import EventAccess, require_event_role, require_verified
from app.db.session import get_session
from app.modules.activation import service
from app.modules.activation.schemas import AcceptTerms, ActivateSales, ActivationChecklist
from app.modules.events.service import get_event
from app.modules.payments.schemas import PaymentOut
from app.modules.users.models import User

router = APIRouter(prefix="/events/{event_id}/paid-sales", tags=["paid-sales activation"])
event_owner = require_event_role()


async def owner(
    access: EventAccess = Depends(event_owner), user: User = Depends(require_verified)
) -> User:
    return user


@router.get("/checklist", response_model=ActivationChecklist)
async def checklist(
    event_id: uuid.UUID, user: User = Depends(owner), session: AsyncSession = Depends(get_session)
):
    return await service.checklist(session, await get_event(session, event_id))


@router.post("/terms", response_model=ActivationChecklist, summary="Accept paid-event terms")
async def terms(
    event_id: uuid.UUID,
    data: AcceptTerms,
    user: User = Depends(owner),
    session: AsyncSession = Depends(get_session),
):
    return await service.accept_terms(session, event_id, user)


@router.post(
    "/pay",
    response_model=PaymentOut,
    status_code=201,
    summary="Start or reuse a simulated activation-fee payment",
)
async def pay(
    event_id: uuid.UUID, user: User = Depends(owner), session: AsyncSession = Depends(get_session)
):
    return await service.pay(session, event_id, user)


@router.post(
    "/activate", response_model=ActivationChecklist, summary="Enable paid sales for this event"
)
async def activate(
    event_id: uuid.UUID,
    data: ActivateSales,
    user: User = Depends(owner),
    session: AsyncSession = Depends(get_session),
):
    return await service.activate(session, event_id, user, data.payout_account_id)
