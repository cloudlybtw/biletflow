from typing import Annotated, Literal

from pydantic import BaseModel, EmailStr, Field

from app.modules.users.schemas import FullName, Locale, UserOut

Password = Annotated[str, Field(min_length=8, max_length=128)]


class RegisterRequest(BaseModel):
    email: EmailStr
    password: Password
    full_name: FullName
    locale: Locale = "ru"


class VerifyEmailRequest(BaseModel):
    token: str = Field(
        min_length=1, max_length=200, description="The `token` query parameter from the link."
    )


class ResendVerificationRequest(BaseModel):
    email: EmailStr


class LoginRequest(BaseModel):
    email: EmailStr
    # Not length-checked: a wrong password must fail as INVALID_CREDENTIALS, not 422.
    password: str = Field(max_length=1024)


class TokenResponse(BaseModel):
    access_token: str = Field(description="JWT for `Authorization: Bearer ...`.")
    token_type: Literal["bearer"] = "bearer"
    expires_in: int = Field(description="Access token lifetime in seconds.")
    refresh_token: str = Field(
        description="Single-use: exchange it at `POST /auth/refresh` for a new pair."
    )
    user: UserOut


class RefreshRequest(BaseModel):
    # Generous limit so a wrong token (e.g. an access JWT) fails as 401, not 422.
    refresh_token: str = Field(min_length=1, max_length=2048)


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str = Field(
        min_length=1, max_length=200, description="The `token` query parameter from the link."
    )
    new_password: Password
