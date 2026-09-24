import uuid
from datetime import UTC, datetime

from fastapi import status
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import (
    NOT_FOUND,
    ORGANIZER_PROFILE_EXISTS,
    ORGANIZER_PROFILE_NOT_FOUND,
    PAYOUT_ACCOUNT_EXISTS,
    PAYOUT_ACCOUNT_NOT_ACTIVE,
    AppError,
)
from app.core.pagination import Pagination
from app.modules.history import service as history
from app.modules.organizers.models import (
    OrganizerProfile,
    PayoutAccount,
    PayoutAccountStatus,
    VerificationStatus,
)
from app.modules.organizers.schemas import (
    OrganizerProfileCreate,
    OrganizerProfileUpdate,
    PayoutAccountCreate,
)
from app.modules.users.models import User

SIMULATED_PAYOUT_PROVIDER = "biletflow_sim"
ACTOR_ROLE = "organizer"


async def create_profile(
    session: AsyncSession, user: User, data: OrganizerProfileCreate
) -> OrganizerProfile:
    """Become an organizer: at most one profile per user (unique user_id)."""
    profile = OrganizerProfile(
        user_id=user.id,
        display_name=data.display_name,
        contact_email=data.contact_email or user.email,
        contact_phone=data.contact_phone,
        description=data.description,
    )
    try:
        session.add(profile)
        await session.flush()
    except IntegrityError as exc:
        await session.rollback()
        raise AppError(
            ORGANIZER_PROFILE_EXISTS,
            "You already have an organizer profile.",
            status.HTTP_409_CONFLICT,
        ) from exc
    await history.record(
        session,
        actor_user_id=user.id,
        actor_role=ACTOR_ROLE,
        action_type="organizer_profile.created",
        entity_type="organizer_profile",
        entity_id=profile.id,
        summary=f"Organizer profile '{profile.display_name}' created",
    )
    await session.commit()
    return profile


async def get_profile(
    session: AsyncSession, user: User, *, for_update: bool = False
) -> OrganizerProfile:
    query = select(OrganizerProfile).where(OrganizerProfile.user_id == user.id)
    if for_update:
        query = query.with_for_update()
    profile = await session.scalar(query)
    if profile is None:
        raise AppError(
            ORGANIZER_PROFILE_NOT_FOUND,
            "You don't have an organizer profile yet.",
            status.HTTP_404_NOT_FOUND,
        )
    return profile


async def update_profile(
    session: AsyncSession, user: User, data: OrganizerProfileUpdate
) -> OrganizerProfile:
    profile = await get_profile(session, user)
    changes = {}
    for field, value in data.model_dump(exclude_unset=True).items():
        old = getattr(profile, field)
        if old != value:
            changes[field] = {"from": old, "to": value}
            setattr(profile, field, value)
    if changes:
        await history.record(
            session,
            actor_user_id=user.id,
            actor_role=ACTOR_ROLE,
            action_type="organizer_profile.updated",
            entity_type="organizer_profile",
            entity_id=profile.id,
            summary=f"Organizer profile updated: {', '.join(sorted(changes))}",
            metadata={"changes": changes},
        )
    await session.commit()
    return profile


async def verify_identity(session: AsyncSession, user: User) -> OrganizerProfile:
    """Simulated identity check: always succeeds (no KYC in the MVP, SRS §8)."""
    profile = await get_profile(session, user, for_update=True)
    if profile.verification_status == VerificationStatus.VERIFIED:
        await session.commit()  # release the lock; rollback would expire `profile`
        return profile
    profile.verification_status = VerificationStatus.VERIFIED
    profile.verified_at = datetime.now(UTC)
    await history.record(
        session,
        actor_user_id=user.id,
        actor_role=ACTOR_ROLE,
        action_type="organizer_profile.identity_verified",
        entity_type="organizer_profile",
        entity_id=profile.id,
        summary="Identity verified (simulated)",
        metadata={"simulated": True},
    )
    await session.commit()
    return profile


async def list_payout_accounts(
    session: AsyncSession, user: User, page: Pagination
) -> tuple[list[PayoutAccount], int]:
    profile = await get_profile(session, user)
    where = PayoutAccount.organizer_profile_id == profile.id
    total = await session.scalar(select(func.count()).select_from(PayoutAccount).where(where))
    accounts = await session.scalars(
        select(PayoutAccount)
        .where(where)
        .order_by(PayoutAccount.created_at, PayoutAccount.id)
        .limit(page.limit)
        .offset(page.offset)
    )
    return list(accounts.all()), total or 0


async def add_payout_account(
    session: AsyncSession, user: User, data: PayoutAccountCreate
) -> PayoutAccount:
    """Register a simulated payout account; active at once, default if it's the first."""
    # Lock the profile so concurrent adds agree on which one becomes default.
    profile = await get_profile(session, user, for_update=True)
    has_default = await session.scalar(
        select(PayoutAccount.id).where(
            PayoutAccount.organizer_profile_id == profile.id, PayoutAccount.is_default
        )
    )
    account = PayoutAccount(
        organizer_profile_id=profile.id,
        provider=SIMULATED_PAYOUT_PROVIDER,
        external_account_ref=data.external_account_ref,
        account_holder_name=data.account_holder_name,
        status=PayoutAccountStatus.ACTIVE,
        is_default=has_default is None,
        is_simulated=True,
    )
    try:
        session.add(account)
        await session.flush()
    except IntegrityError as exc:
        await session.rollback()
        raise AppError(
            PAYOUT_ACCOUNT_EXISTS,
            "This payout account is already registered.",
            status.HTTP_409_CONFLICT,
        ) from exc
    await history.record(
        session,
        actor_user_id=user.id,
        actor_role=ACTOR_ROLE,
        action_type="payout_account.added",
        entity_type="payout_account",
        entity_id=account.id,
        summary=f"Payout account ending {account.external_account_ref[-4:]} added (simulated)",
        metadata={"simulated": True, "is_default": account.is_default},
    )
    await session.commit()
    return account


async def set_default_payout_account(
    session: AsyncSession, user: User, account_id: uuid.UUID
) -> PayoutAccount:
    # Lock the profile so concurrent calls can't both clear and set a default,
    # which uq_payout_accounts_default would then reject.
    profile = await get_profile(session, user, for_update=True)
    account = await session.scalar(
        select(PayoutAccount).where(
            PayoutAccount.id == account_id, PayoutAccount.organizer_profile_id == profile.id
        )
    )
    if account is None:
        raise AppError(NOT_FOUND, "Payout account not found.", status.HTTP_404_NOT_FOUND)
    if account.is_default:
        await session.commit()  # release the lock; rollback would expire `account`
        return account
    if account.status != PayoutAccountStatus.ACTIVE:
        raise AppError(
            PAYOUT_ACCOUNT_NOT_ACTIVE,
            "Only an active payout account can be the default.",
            status.HTTP_409_CONFLICT,
        )
    await session.execute(
        update(PayoutAccount)
        .where(PayoutAccount.organizer_profile_id == profile.id, PayoutAccount.is_default)
        .values(is_default=False)
    )
    account.is_default = True
    await history.record(
        session,
        actor_user_id=user.id,
        actor_role=ACTOR_ROLE,
        action_type="payout_account.default_set",
        entity_type="payout_account",
        entity_id=account.id,
        summary=f"Payout account ending {account.external_account_ref[-4:]} set as default",
    )
    await session.commit()
    return account
