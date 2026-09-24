import uuid
from datetime import UTC, datetime, timedelta

import jwt
import pytest

from app.core.config import get_settings
from app.core.security import (
    AccessTokenError,
    AccessTokenExpiredError,
    create_access_token,
    decode_access_token,
    hash_password,
    hash_token,
    new_opaque_token,
    verify_password,
)


def test_password_hash_is_argon2_and_verifies():
    password_hash = hash_password("s3cret-pass")

    assert password_hash.startswith("$argon2id$")
    assert verify_password(password_hash, "s3cret-pass")
    assert not verify_password(password_hash, "wrong-pass")


def test_verify_password_rejects_malformed_hash():
    assert not verify_password("not-a-hash", "anything")


def test_opaque_token_stores_only_sha256_hash():
    raw, token_hash = new_opaque_token()

    assert raw not in token_hash
    assert token_hash == hash_token(raw)
    assert len(token_hash) == 64


def test_access_token_round_trips_user_id():
    user_id = uuid.uuid4()

    token, expires_in = create_access_token(user_id)

    assert decode_access_token(token) == user_id
    assert expires_in == 15 * 60


def test_access_token_rejects_tampering():
    token, _ = create_access_token(uuid.uuid4())
    header, payload, signature = token.split(".")
    tampered = f"{header}.{payload}.{signature[:-2]}AA"

    with pytest.raises(AccessTokenError):
        decode_access_token(tampered)


def test_access_token_rejects_non_uuid_subject():
    settings = get_settings()
    token = jwt.encode(
        {"sub": "admin", "typ": "access", "exp": datetime.now(UTC) + timedelta(minutes=1)},
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )

    with pytest.raises(AccessTokenError):
        decode_access_token(token)


def test_expired_access_token_raises_expired_error():
    settings = get_settings()
    token = jwt.encode(
        {"sub": str(uuid.uuid4()), "typ": "access", "exp": datetime.now(UTC) - timedelta(1)},
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )

    with pytest.raises(AccessTokenExpiredError):
        decode_access_token(token)
