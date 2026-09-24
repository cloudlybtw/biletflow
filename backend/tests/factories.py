"""Shared test data helpers.

Use these instead of copied setup blocks — see CLAUDE.md's Testing section.
Factories flush (so server defaults are populated) but don't commit; the
caller's session owns the transaction.
"""

import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import column, insert, table
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token, hash_password, new_opaque_token
from app.modules.auth.models import UserToken, UserTokenPurpose
from app.modules.organizers.models import OrganizerProfile, PayoutAccount, PayoutAccountStatus
from app.modules.users.models import StaffAssignment, StaffRole, User

DEFAULT_PASSWORD = "correct-horse-battery"
# Hashing is deliberately slow; reuse one hash for factory-made users.
_DEFAULT_PASSWORD_HASH = hash_password(DEFAULT_PASSWORD)


def unique_suffix() -> str:
    return secrets.token_hex(4)


def unique_email(prefix: str = "user") -> str:
    return f"{prefix}+{unique_suffix()}@example.com"


async def create_user(session: AsyncSession, **overrides: Any) -> User:
    fields: dict[str, Any] = {
        "email": unique_email(),
        "password_hash": _DEFAULT_PASSWORD_HASH,
        "full_name": "Test User",
    }
    fields.update(overrides)
    user = User(**fields)
    session.add(user)
    await session.flush()
    return user


async def create_organizer(
    session: AsyncSession, user: User | None = None, **overrides: Any
) -> OrganizerProfile:
    if user is None:
        user = await create_user(session)
    fields: dict[str, Any] = {
        "user_id": user.id,
        "display_name": f"Organizer {unique_suffix()}",
        "contact_email": user.email,
    }
    fields.update(overrides)
    profile = OrganizerProfile(**fields)
    session.add(profile)
    await session.flush()
    return profile


async def create_user_token(
    session: AsyncSession,
    user: User,
    purpose: UserTokenPurpose = UserTokenPurpose.EMAIL_VERIFY,
    **overrides: Any,
) -> tuple[str, UserToken]:
    """Return (raw token, stored row); only the hash is persisted, as in production."""
    raw, token_hash = new_opaque_token()
    fields: dict[str, Any] = {
        "user_id": user.id,
        "purpose": purpose,
        "token_hash": token_hash,
        "expires_at": datetime.now(UTC) + timedelta(hours=24),
    }
    fields.update(overrides)
    token = UserToken(**fields)
    session.add(token)
    await session.flush()
    return raw, token


def auth_headers(user: User) -> dict[str, str]:
    """Authorization header with a fresh access token for `user`."""
    token, _ = create_access_token(user.id)
    return {"Authorization": f"Bearer {token}"}


async def create_verified_user(session: AsyncSession, **overrides: Any) -> User:
    return await create_user(session, email_verified_at=datetime.now(UTC), **overrides)


# Minimal insert until the Event model and its factory land in M2.
_events = table(
    "events",
    column("id"),
    column("organizer_profile_id"),
    column("title"),
    column("slug"),
    column("starts_at"),
    column("ends_at"),
)


async def create_event(
    session: AsyncSession, organizer: OrganizerProfile | None = None, **overrides: Any
) -> uuid.UUID:
    """Insert a draft event row and return its id."""
    if organizer is None:
        organizer = await create_organizer(session)
    starts_at = datetime.now(UTC) + timedelta(days=30)
    fields: dict[str, Any] = {
        "organizer_profile_id": organizer.id,
        "title": "Test Event",
        "slug": f"test-event-{unique_suffix()}",
        "starts_at": starts_at,
        "ends_at": starts_at + timedelta(hours=3),
    }
    fields.update(overrides)
    return await session.scalar(insert(_events).values(**fields).returning(_events.c.id))


async def create_staff_assignment(
    session: AsyncSession, event_id: uuid.UUID, user: User, role: StaffRole, **overrides: Any
) -> StaffAssignment:
    assignment = StaffAssignment(event_id=event_id, user_id=user.id, role=role, **overrides)
    session.add(assignment)
    await session.flush()
    return assignment


async def create_payout_account(
    session: AsyncSession, organizer: OrganizerProfile, **overrides: Any
) -> PayoutAccount:
    fields: dict[str, Any] = {
        "organizer_profile_id": organizer.id,
        "provider": "biletflow_sim",
        "external_account_ref": f"KZ{secrets.randbelow(10**18):018d}",
        "account_holder_name": "Test Holder",
        "status": PayoutAccountStatus.ACTIVE,
    }
    fields.update(overrides)
    account = PayoutAccount(**fields)
    session.add(account)
    await session.flush()
    return account
