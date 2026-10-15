import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import require_verified
from app.db.session import get_session
from app.modules.payments import service
from app.modules.payments.schemas import PaymentOut, PaymentSimulate
from app.modules.users.models import User

router = APIRouter(prefix="/payments", tags=["payments"])


@router.post(
    "/{payment_id}/simulate",
    response_model=PaymentOut,
    summary="Finish a demo payment",
    description="The verified order buyer or event owner chooses success or failure for their ticket or activation-fee payment. This is simulated, with no real charge. Repeating the same final outcome is idempotent; changing it is rejected.",
)
async def simulate(
    payment_id: uuid.UUID,
    data: PaymentSimulate,
    user: User = Depends(require_verified),
    session: AsyncSession = Depends(get_session),
):
    return await service.simulate(session, user, payment_id, data.outcome)
