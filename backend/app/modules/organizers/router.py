import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import current_user, require_verified
from app.core.pagination import Page, Pagination, pagination
from app.db.session import get_session
from app.modules.organizers import service
from app.modules.organizers.schemas import (
    IdentityVerificationOut,
    OrganizerProfileCreate,
    OrganizerProfileOut,
    OrganizerProfileUpdate,
    PayoutAccountCreate,
    PayoutAccountOut,
)
from app.modules.users.models import User

router = APIRouter(prefix="/organizers/me", tags=["organizers"])


@router.post(
    "",
    summary="Become an organizer",
    description=(
        "Creates the signed-in user's organizer profile. Requires a verified email "
        "(403 `EMAIL_NOT_VERIFIED`). 409 `ORGANIZER_PROFILE_EXISTS` if there already is one."
    ),
    status_code=status.HTTP_201_CREATED,
    response_model=OrganizerProfileOut,
)
async def create_profile(
    data: OrganizerProfileCreate,
    user: User = Depends(require_verified),
    session: AsyncSession = Depends(get_session),
) -> OrganizerProfileOut:
    profile = await service.create_profile(session, user, data)
    return OrganizerProfileOut.model_validate(profile)


@router.get(
    "",
    summary="Get my organizer profile",
    description="404 `ORGANIZER_PROFILE_NOT_FOUND` if the user isn't an organizer yet.",
    response_model=OrganizerProfileOut,
)
async def get_profile(
    user: User = Depends(current_user), session: AsyncSession = Depends(get_session)
) -> OrganizerProfileOut:
    return OrganizerProfileOut.model_validate(await service.get_profile(session, user))


@router.patch(
    "",
    summary="Update my organizer profile",
    description="Changes only the fields sent. Audited.",
    response_model=OrganizerProfileOut,
)
async def update_profile(
    data: OrganizerProfileUpdate,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> OrganizerProfileOut:
    profile = await service.update_profile(session, user, data)
    return OrganizerProfileOut.model_validate(profile)


@router.post(
    "/identity-verification",
    summary="Verify organizer identity (simulated)",
    description=(
        "Demo stand-in for identity verification (SRS §3.2): immediately sets "
        "`verification_status` to `verified`. Repeating it is a no-op. No documents are "
        "collected."
    ),
    response_model=IdentityVerificationOut,
)
async def verify_identity(
    user: User = Depends(current_user), session: AsyncSession = Depends(get_session)
) -> IdentityVerificationOut:
    return IdentityVerificationOut.model_validate(await service.verify_identity(session, user))


@router.get(
    "/payout-accounts",
    summary="List my payout accounts",
    response_model=Page[PayoutAccountOut],
)
async def list_payout_accounts(
    page: Pagination = Depends(pagination),
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> Page[PayoutAccountOut]:
    accounts, total = await service.list_payout_accounts(session, user, page)
    return Page(items=[PayoutAccountOut.model_validate(a) for a in accounts], total=total)


@router.post(
    "/payout-accounts",
    summary="Add a payout account (simulated)",
    description=(
        "Registers a simulated payout account (provider `biletflow_sim`). It is active "
        "immediately and becomes the default if it's the first one. 409 "
        "`PAYOUT_ACCOUNT_EXISTS` if the account reference is already registered."
    ),
    status_code=status.HTTP_201_CREATED,
    response_model=PayoutAccountOut,
)
async def add_payout_account(
    data: PayoutAccountCreate,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> PayoutAccountOut:
    account = await service.add_payout_account(session, user, data)
    return PayoutAccountOut.model_validate(account)


@router.post(
    "/payout-accounts/{account_id}/default",
    summary="Make a payout account the default",
    description="The previous default is cleared. 409 `PAYOUT_ACCOUNT_NOT_ACTIVE` if disabled.",
    response_model=PayoutAccountOut,
)
async def set_default_payout_account(
    account_id: uuid.UUID,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> PayoutAccountOut:
    account = await service.set_default_payout_account(session, user, account_id)
    return PayoutAccountOut.model_validate(account)
