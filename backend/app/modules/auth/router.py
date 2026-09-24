from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.modules.auth import service
from app.modules.auth.schemas import (
    ForgotPasswordRequest,
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    ResendVerificationRequest,
    ResetPasswordRequest,
    TokenResponse,
    VerifyEmailRequest,
)
from app.modules.users.schemas import UserOut

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/register",
    summary="Register a new account",
    description=(
        "Creates an unverified attendee account and queues a verification email. "
        "Returns 409 `EMAIL_TAKEN` if the email (case-insensitive) is already registered. "
        "Does not sign the user in; use login afterwards."
    ),
    status_code=status.HTTP_201_CREATED,
    response_model=UserOut,
)
async def register(data: RegisterRequest, session: AsyncSession = Depends(get_session)) -> UserOut:
    user = await service.register(session, data)
    return UserOut.from_user(user)


@router.post(
    "/verify-email",
    summary="Verify an email address",
    description=(
        "Redeems the token from the verification link (`/verify-email?token=...` on the web "
        "app) and returns the verified user. Posting an already-redeemed token for a "
        "verified user returns 200 again. Errors: 400 `VERIFICATION_TOKEN_EXPIRED` "
        "(offer a resend), 400 `VERIFICATION_TOKEN_INVALID` (unknown, or superseded by a "
        "newer link)."
    ),
    response_model=UserOut,
)
async def verify_email(
    data: VerifyEmailRequest, session: AsyncSession = Depends(get_session)
) -> UserOut:
    user = await service.verify_email(session, data.token)
    return UserOut.from_user(user)


@router.post(
    "/verify-email/resend",
    summary="Resend the verification email",
    description=(
        "Queues a new verification link for an unverified account and invalidates older "
        "links. Always returns 202, whether or not the email is registered or already "
        "verified; repeated requests within a short cooldown send nothing new."
    ),
    status_code=status.HTTP_202_ACCEPTED,
    response_class=Response,
)
async def resend_verification(
    data: ResendVerificationRequest, session: AsyncSession = Depends(get_session)
) -> Response:
    await service.resend_verification(session, data.email)
    return Response(status_code=status.HTTP_202_ACCEPTED)


@router.post(
    "/login",
    summary="Sign in",
    description=(
        "Returns a 15-minute access token (send as `Authorization: Bearer ...`) and a "
        "single-use refresh token. Unverified accounts can sign in; actions that need a "
        "verified email return 403 `EMAIL_NOT_VERIFIED`. Errors: 401 `INVALID_CREDENTIALS`, "
        "403 `ACCOUNT_SUSPENDED`."
    ),
    response_model=TokenResponse,
)
async def login(data: LoginRequest, session: AsyncSession = Depends(get_session)) -> TokenResponse:
    return await service.login(session, data.email, data.password)


@router.post(
    "/refresh",
    summary="Refresh the access token",
    description=(
        "Exchanges a refresh token for a new access token and a new refresh token; the old "
        "refresh token stops working (rotation). Call it once per expiry: a second call with "
        "the same token fails. Errors: 401 `REFRESH_TOKEN_INVALID` (sign in again), "
        "403 `ACCOUNT_SUSPENDED`."
    ),
    response_model=TokenResponse,
)
async def refresh(
    data: RefreshRequest, session: AsyncSession = Depends(get_session)
) -> TokenResponse:
    return await service.refresh(session, data.refresh_token)


@router.post(
    "/logout",
    summary="Sign out",
    description=(
        "Revokes the given refresh token (this device only). Always returns 204. The access "
        "token stays valid until it expires, so clients should discard it."
    ),
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
)
async def logout(data: RefreshRequest, session: AsyncSession = Depends(get_session)) -> Response:
    await service.logout(session, data.refresh_token)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/password/forgot",
    summary="Request a password reset email",
    description=(
        "Emails a single-use reset link (`/reset-password?token=...` on the web app, valid "
        "60 minutes) and invalidates older links. Always returns 202, whether or not the "
        "email is registered; repeated requests within a short cooldown send nothing new."
    ),
    status_code=status.HTTP_202_ACCEPTED,
    response_class=Response,
)
async def forgot_password(
    data: ForgotPasswordRequest, session: AsyncSession = Depends(get_session)
) -> Response:
    await service.forgot_password(session, data.email)
    return Response(status_code=status.HTTP_202_ACCEPTED)


@router.post(
    "/password/reset",
    summary="Set a new password with a reset link",
    description=(
        "Sets the new password, marks the email verified, and signs out every session "
        "(all refresh tokens revoked). Sign in again afterwards. Errors: 400 "
        "`RESET_TOKEN_EXPIRED` (request a new link), 400 `RESET_TOKEN_INVALID` (unknown, "
        "already used, or superseded)."
    ),
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
)
async def reset_password(
    data: ResetPasswordRequest, session: AsyncSession = Depends(get_session)
) -> Response:
    await service.reset_password(session, data.token, data.new_password)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
