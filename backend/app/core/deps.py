"""Authentication and permission dependencies shared by every router.

Every protected route depends on `current_user` (directly or through one of
the `require_*` dependencies below), so suspension and deletion take effect on
the next request, not when the access token expires.
"""

import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from fastapi import Depends, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import (
    ACCOUNT_SUSPENDED,
    EMAIL_NOT_VERIFIED,
    FORBIDDEN,
    NOT_FOUND,
    TOKEN_EXPIRED,
    UNAUTHORIZED,
    AppError,
)
from app.core.security import AccessTokenError, AccessTokenExpiredError, decode_access_token
from app.db.session import get_session
from app.modules.users import service as users_service
from app.modules.users.models import PlatformRole, StaffRole, User, UserStatus

_bearer = HTTPBearer(auto_error=False, description="Access token from `POST /auth/login`.")


async def current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    session: AsyncSession = Depends(get_session),
) -> User:
    """The signed-in, non-suspended user. 401 `TOKEN_EXPIRED` means: refresh and retry."""
    if credentials is None:
        raise AppError(UNAUTHORIZED, "Authentication required.", status.HTTP_401_UNAUTHORIZED)
    try:
        user_id = decode_access_token(credentials.credentials)
    except AccessTokenExpiredError as exc:
        raise AppError(
            TOKEN_EXPIRED, "Access token has expired.", status.HTTP_401_UNAUTHORIZED
        ) from exc
    except AccessTokenError as exc:
        raise AppError(UNAUTHORIZED, "Invalid access token.", status.HTTP_401_UNAUTHORIZED) from exc

    user = await users_service.get_user(session, user_id)
    if user is None or user.status == UserStatus.DELETED:
        raise AppError(UNAUTHORIZED, "Invalid access token.", status.HTTP_401_UNAUTHORIZED)
    if user.status == UserStatus.SUSPENDED:
        raise AppError(ACCOUNT_SUSPENDED, "This account is suspended.", status.HTTP_403_FORBIDDEN)
    return user


async def require_verified(user: User = Depends(current_user)) -> User:
    if user.email_verified_at is None:
        raise AppError(
            EMAIL_NOT_VERIFIED,
            "Verify your email address to continue.",
            status.HTTP_403_FORBIDDEN,
        )
    return user


async def require_platform_admin(user: User = Depends(current_user)) -> User:
    if user.platform_role != PlatformRole.PLATFORM_ADMIN:
        raise AppError(FORBIDDEN, "Platform admin access required.", status.HTTP_403_FORBIDDEN)
    return user


@dataclass(frozen=True)
class EventAccess:
    """What the acting user may do on one event; returned by `require_event_role`."""

    user: User
    event_id: uuid.UUID
    is_owner: bool
    staff_roles: frozenset[StaffRole]
    is_platform_admin: bool

    @property
    def actor_role(self) -> str:
        """Label for `audit_logs.actor_role`."""
        if self.is_owner:
            return "organizer"
        if self.staff_roles:
            return sorted(self.staff_roles)[0].value
        return PlatformRole.PLATFORM_ADMIN.value


def require_event_role(
    *roles: StaffRole, allow_platform_admin: bool = False
) -> Callable[..., Awaitable[EventAccess]]:
    """Dependency factory for routes with an `{event_id}` path parameter.

    The event's organizer always passes. Staff pass with an active assignment in
    one of `roles` (none given = organizer only). Platform admins pass only when
    `allow_platform_admin` (read-only moderation views). Users with no
    relationship to the event get 404, so private and draft events stay hidden;
    staff without the required role get 403.
    """

    async def dependency(
        event_id: uuid.UUID,
        user: User = Depends(current_user),
        session: AsyncSession = Depends(get_session),
    ) -> EventAccess:
        relation = await users_service.get_event_relation(session, event_id, user.id)
        if relation is None:
            raise AppError(NOT_FOUND, "Event not found.", status.HTTP_404_NOT_FOUND)
        access = EventAccess(
            user=user,
            event_id=event_id,
            is_owner=relation.is_owner,
            staff_roles=relation.staff_roles,
            is_platform_admin=user.platform_role == PlatformRole.PLATFORM_ADMIN,
        )
        if access.is_owner or access.staff_roles & set(roles):
            return access
        if allow_platform_admin and access.is_platform_admin:
            return access
        if access.staff_roles or access.is_platform_admin:
            raise AppError(
                FORBIDDEN,
                "You don't have permission for this action on this event.",
                status.HTTP_403_FORBIDDEN,
            )
        raise AppError(NOT_FOUND, "Event not found.", status.HTTP_404_NOT_FOUND)

    return dependency
