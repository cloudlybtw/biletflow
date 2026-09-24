import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

from app.core.config import get_settings

_password_hasher = PasswordHasher()
# Verified against when the email is unknown, so login takes the same time
# whether or not the account exists.
_DUMMY_PASSWORD_HASH = _password_hasher.hash(secrets.token_urlsafe(16))

ACCESS_TOKEN_TYPE = "access"


class AccessTokenError(Exception):
    """The access token is missing, malformed, tampered with or of the wrong type."""


class AccessTokenExpiredError(AccessTokenError):
    pass


def hash_password(password: str) -> str:
    return _password_hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return _password_hasher.verify(password_hash, password)
    except (VerificationError, InvalidHashError):
        return False


def burn_password_check(password: str) -> None:
    """Spend the time of a real verify when there is no user to check against."""
    verify_password(_DUMMY_PASSWORD_HASH, password)


def hash_token(raw_token: str) -> str:
    """SHA-256 hex digest; refresh/verification/reset tokens are stored only like this."""
    return hashlib.sha256(raw_token.encode()).hexdigest()


def new_opaque_token() -> tuple[str, str]:
    """Return (raw token to hand to the user, hash to store)."""
    raw = secrets.token_urlsafe(32)
    return raw, hash_token(raw)


def create_access_token(user_id: uuid.UUID) -> tuple[str, int]:
    """Return (signed JWT, lifetime in seconds). The only claim that matters is `sub`."""
    settings = get_settings()
    lifetime = timedelta(minutes=settings.access_token_expire_minutes)
    now = datetime.now(UTC)
    claims = {"sub": str(user_id), "typ": ACCESS_TOKEN_TYPE, "iat": now, "exp": now + lifetime}
    token = jwt.encode(claims, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    return token, int(lifetime.total_seconds())


def decode_access_token(token: str) -> uuid.UUID:
    """Return the user id from a valid access token, or raise AccessTokenError."""
    settings = get_settings()
    try:
        claims = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
            options={"require": ["sub", "exp", "typ"]},
        )
    except jwt.ExpiredSignatureError as exc:
        raise AccessTokenExpiredError from exc
    except jwt.InvalidTokenError as exc:
        raise AccessTokenError from exc
    if claims["typ"] != ACCESS_TOKEN_TYPE:
        raise AccessTokenError
    try:
        return uuid.UUID(claims["sub"])
    except ValueError as exc:
        raise AccessTokenError from exc
