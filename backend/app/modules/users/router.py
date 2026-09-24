from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import current_user
from app.db.session import get_session
from app.modules.users import service
from app.modules.users.models import User
from app.modules.users.schemas import MeOut, UpdateMeRequest

router = APIRouter(prefix="/me", tags=["users"])


@router.get("", summary="Get the signed-in user", response_model=MeOut)
async def get_me(
    user: User = Depends(current_user), session: AsyncSession = Depends(get_session)
) -> MeOut:
    return MeOut.from_user_and_role(user, await service.is_organizer(session, user.id))


@router.patch(
    "",
    summary="Update the signed-in user's profile",
    description="Changes only the fields sent: `full_name`, `phone` (`null` removes it), `locale`.",
    response_model=MeOut,
)
async def update_me(
    data: UpdateMeRequest,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> MeOut:
    user = await service.update_me(session, user, data)
    return MeOut.from_user_and_role(user, await service.is_organizer(session, user.id))
