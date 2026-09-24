import uuid
from datetime import UTC, datetime, timedelta
from urllib.parse import urlencode

from fastapi import status
from fastapi.concurrency import run_in_threadpool
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import (
    ACCOUNT_SUSPENDED,
    EMAIL_TAKEN,
    INVALID_CREDENTIALS,
    REFRESH_TOKEN_INVALID,
    RESET_TOKEN_EXPIRED,
    RESET_TOKEN_INVALID,
    VERIFICATION_TOKEN_EXPIRED,
    VERIFICATION_TOKEN_INVALID,
    AppError,
)
from app.core.security import (
    burn_password_check,
    create_access_token,
    hash_password,
    hash_token,
    new_opaque_token,
    verify_password,
)
from app.modules.auth.models import UserToken, UserTokenPurpose
from app.modules.auth.schemas import RegisterRequest, TokenResponse
from app.modules.notifications import service as notifications
from app.modules.notifications.models import NotificationChannel, NotificationType
from app.modules.users.models import User, UserStatus
from app.modules.users.schemas import UserOut


async def register(session: AsyncSession, data: RegisterRequest) -> User:
    """Create an unverified account and queue its verification email (SRS §4.1)."""
    # argon2 is CPU-bound by design; keep it off the event loop.
    password_hash = await run_in_threadpool(hash_password, data.password)
    user = User(
        email=data.email,
        password_hash=password_hash,
        full_name=data.full_name,
        locale=data.locale,
    )
    try:
        session.add(user)
        # uq on users.email (CITEXT) is the duplicate guard, also under concurrency.
        await session.flush()
    except IntegrityError as exc:
        await session.rollback()
        raise AppError(
            EMAIL_TAKEN,
            "An account with this email already exists.",
            status.HTTP_409_CONFLICT,
        ) from exc

    await _issue_email_verification(session, user)
    await session.commit()
    return user


async def verify_email(session: AsyncSession, raw_token: str) -> User:
    """Redeem a single-use email verification token and mark the user verified."""
    user_id = await _claim_token(session, raw_token, UserTokenPurpose.EMAIL_VERIFY)
    if user_id is not None:
        await session.execute(
            update(User)
            .where(User.id == user_id, User.email_verified_at.is_(None))
            .values(email_verified_at=func.now())
        )
        await _revoke_tokens(session, user_id, UserTokenPurpose.EMAIL_VERIFY)
        await session.commit()
        return await _load_user(session, user_id)

    token = await _find_token(session, raw_token, UserTokenPurpose.EMAIL_VERIFY)
    if token is None:
        raise AppError(VERIFICATION_TOKEN_INVALID, "Verification link is invalid.")
    if token.used_at is None:
        raise AppError(VERIFICATION_TOKEN_EXPIRED, "Verification link has expired.")
    user = await _load_user(session, token.user_id)
    if user.email_verified_at is None:
        # Used without verifying: superseded by a newer link from resend.
        raise AppError(VERIFICATION_TOKEN_INVALID, "Verification link is invalid.")
    # Link opened twice (or page reloaded) after success: idempotent.
    return user


async def resend_verification(session: AsyncSession, email: str) -> None:
    """Issue a fresh verification link, invalidating older ones.

    Silently does nothing for unknown, verified or inactive accounts, and
    within the cooldown, so the response never reveals account state.
    """
    settings = get_settings()
    # Lock the user row so concurrent resends don't both pass the cooldown.
    user = await session.scalar(select(User).where(User.email == email).with_for_update())
    if (
        user is None
        or user.email_verified_at is not None
        or user.status != UserStatus.ACTIVE
        or await _within_cooldown(
            session,
            user.id,
            UserTokenPurpose.EMAIL_VERIFY,
            settings.email_verify_resend_cooldown_seconds,
        )
    ):
        await session.rollback()
        return

    await _revoke_tokens(session, user.id, UserTokenPurpose.EMAIL_VERIFY)
    await _issue_email_verification(session, user)
    await session.commit()


async def login(session: AsyncSession, email: str, password: str) -> TokenResponse:
    """Check credentials and start a session: access JWT plus a stored refresh token."""
    user = await session.scalar(select(User).where(User.email == email))
    if user is None or user.status == UserStatus.DELETED:
        await run_in_threadpool(burn_password_check, password)
        raise _invalid_credentials()
    if not await run_in_threadpool(verify_password, user.password_hash, password):
        raise _invalid_credentials()
    # Checked after the password so account state is revealed only to its owner.
    if user.status == UserStatus.SUSPENDED:
        raise _account_suspended()

    user.last_login_at = datetime.now(UTC)
    response = await _start_session(session, user)
    await session.commit()
    return response


async def refresh(session: AsyncSession, raw_token: str) -> TokenResponse:
    """Rotate a refresh token: the presented one is used up and a new pair issued."""
    user_id = await _claim_token(session, raw_token, UserTokenPurpose.REFRESH)
    if user_id is None:
        await session.rollback()
        raise AppError(
            REFRESH_TOKEN_INVALID,
            "Refresh token is invalid, expired or already used. Sign in again.",
            status.HTTP_401_UNAUTHORIZED,
        )
    user = await _load_user(session, user_id)
    if user.status != UserStatus.ACTIVE:
        # Keep the token consumed; a suspended account gets no new session.
        await _revoke_tokens(session, user.id, UserTokenPurpose.REFRESH)
        await session.commit()
        if user.status == UserStatus.SUSPENDED:
            raise _account_suspended()
        raise _invalid_credentials()

    response = await _start_session(session, user)
    await session.commit()
    return response


async def logout(session: AsyncSession, raw_token: str) -> None:
    """Revoke one refresh token (this device). Unknown or used tokens are ignored."""
    await session.execute(
        update(UserToken)
        .where(
            UserToken.token_hash == hash_token(raw_token),
            UserToken.purpose == UserTokenPurpose.REFRESH,
            UserToken.used_at.is_(None),
        )
        .values(used_at=func.now())
    )
    await session.commit()


async def forgot_password(session: AsyncSession, email: str) -> None:
    """Email a single-use reset link, invalidating older ones.

    Silently does nothing for unknown or inactive accounts, and within the
    cooldown, so the response never reveals account state.
    """
    settings = get_settings()
    user = await session.scalar(select(User).where(User.email == email).with_for_update())
    if (
        user is None
        or user.status != UserStatus.ACTIVE
        or await _within_cooldown(
            session,
            user.id,
            UserTokenPurpose.PASSWORD_RESET,
            settings.password_reset_cooldown_seconds,
        )
    ):
        await session.rollback()
        return

    await _revoke_tokens(session, user.id, UserTokenPurpose.PASSWORD_RESET)
    raw_token, token_hash = new_opaque_token()
    session.add(
        UserToken(
            user_id=user.id,
            purpose=UserTokenPurpose.PASSWORD_RESET,
            token_hash=token_hash,
            expires_at=datetime.now(UTC) + timedelta(minutes=settings.password_reset_token_minutes),
        )
    )
    # Like verify_url, reset_url carries the raw token and is scrubbed by the
    # sender (M7.3) after delivery.
    reset_url = f"{settings.web_base_url}/reset-password?{urlencode({'token': raw_token})}"
    await notifications.enqueue(
        session,
        user_id=user.id,
        type=NotificationType.PASSWORD_RESET,
        channel=NotificationChannel.EMAIL,
        template_key="password_reset",
        payload={"full_name": user.full_name, "locale": user.locale, "reset_url": reset_url},
        related_entity_type="user",
        related_entity_id=str(user.id),
    )
    await session.commit()


async def reset_password(session: AsyncSession, raw_token: str, new_password: str) -> None:
    """Redeem a reset token: set the password and sign out every session."""
    password_hash = await run_in_threadpool(hash_password, new_password)
    user_id = await _claim_token(session, raw_token, UserTokenPurpose.PASSWORD_RESET)
    if user_id is None:
        token = await _find_token(session, raw_token, UserTokenPurpose.PASSWORD_RESET)
        expired = token is not None and token.used_at is None
        await session.rollback()
        if expired:
            raise AppError(RESET_TOKEN_EXPIRED, "Password reset link has expired.")
        # Unknown, already used, or superseded by a newer link.
        raise AppError(RESET_TOKEN_INVALID, "Password reset link is invalid.")

    await session.execute(
        update(User)
        .where(User.id == user_id)
        .values(
            password_hash=password_hash,
            # The link arrived by email, which proves the address.
            email_verified_at=func.coalesce(User.email_verified_at, func.now()),
        )
    )
    await _revoke_tokens(session, user_id, UserTokenPurpose.PASSWORD_RESET)
    await _revoke_tokens(session, user_id, UserTokenPurpose.REFRESH)
    await session.commit()


async def _start_session(session: AsyncSession, user: User) -> TokenResponse:
    """Store a new refresh token (hash only) and pair it with an access token."""
    raw_refresh, refresh_hash = new_opaque_token()
    session.add(
        UserToken(
            user_id=user.id,
            purpose=UserTokenPurpose.REFRESH,
            token_hash=refresh_hash,
            expires_at=datetime.now(UTC) + timedelta(days=get_settings().refresh_token_expire_days),
        )
    )
    await session.flush()
    access_token, expires_in = create_access_token(user.id)
    return TokenResponse(
        access_token=access_token,
        expires_in=expires_in,
        refresh_token=raw_refresh,
        user=UserOut.from_user(user),
    )


def _invalid_credentials() -> AppError:
    return AppError(
        INVALID_CREDENTIALS, "Email or password is incorrect.", status.HTTP_401_UNAUTHORIZED
    )


def _account_suspended() -> AppError:
    return AppError(ACCOUNT_SUSPENDED, "This account is suspended.", status.HTTP_403_FORBIDDEN)


async def _issue_email_verification(session: AsyncSession, user: User) -> None:
    """Store a hashed verification token and queue the email carrying the raw link."""
    settings = get_settings()
    raw_token, token_hash = new_opaque_token()
    session.add(
        UserToken(
            user_id=user.id,
            purpose=UserTokenPurpose.EMAIL_VERIFY,
            token_hash=token_hash,
            expires_at=datetime.now(UTC) + timedelta(hours=settings.email_verify_token_hours),
        )
    )
    # The raw link lives in the outbox payload until sent; the sender (M7.3)
    # scrubs verify_url after delivery. user_tokens only ever holds the hash.
    verify_url = f"{settings.web_base_url}/verify-email?{urlencode({'token': raw_token})}"
    await notifications.enqueue(
        session,
        user_id=user.id,
        type=NotificationType.ACCOUNT_VERIFICATION,
        channel=NotificationChannel.EMAIL,
        template_key="account_verification",
        payload={"full_name": user.full_name, "locale": user.locale, "verify_url": verify_url},
        related_entity_type="user",
        related_entity_id=str(user.id),
    )


async def _revoke_tokens(
    session: AsyncSession, user_id: uuid.UUID, purpose: UserTokenPurpose
) -> None:
    """Mark every unused token of this purpose used (superseded links, logged-out sessions)."""
    await session.execute(
        update(UserToken)
        .where(
            UserToken.user_id == user_id,
            UserToken.purpose == purpose,
            UserToken.used_at.is_(None),
        )
        .values(used_at=func.now())
    )


async def _within_cooldown(
    session: AsyncSession, user_id: uuid.UUID, purpose: UserTokenPurpose, seconds: int
) -> bool:
    """True if a token of this purpose was issued less than `seconds` ago."""
    last_issued = await session.scalar(
        select(func.max(UserToken.created_at)).where(
            UserToken.user_id == user_id, UserToken.purpose == purpose
        )
    )
    return last_issued is not None and datetime.now(UTC) - last_issued < timedelta(seconds=seconds)


async def _claim_token(
    session: AsyncSession, raw_token: str, purpose: UserTokenPurpose
) -> uuid.UUID | None:
    """Atomically mark an unused, unexpired token used; return its user, or None.

    Concurrent requests with the same token serialize on the row lock and only
    one sees used_at IS NULL.
    """
    return await session.scalar(
        update(UserToken)
        .where(
            UserToken.token_hash == hash_token(raw_token),
            UserToken.purpose == purpose,
            UserToken.used_at.is_(None),
            UserToken.expires_at > func.now(),
        )
        .values(used_at=func.now())
        .returning(UserToken.user_id)
    )


async def _find_token(
    session: AsyncSession, raw_token: str, purpose: UserTokenPurpose
) -> UserToken | None:
    return await session.scalar(
        select(UserToken).where(
            UserToken.token_hash == hash_token(raw_token), UserToken.purpose == purpose
        )
    )


async def _load_user(session: AsyncSession, user_id: uuid.UUID) -> User:
    user = await session.scalar(
        select(User).where(User.id == user_id).execution_options(populate_existing=True)
    )
    assert user is not None  # user_tokens.user_id is an FK with ON DELETE CASCADE
    return user
