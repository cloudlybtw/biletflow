import uuid
from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from app.modules.users.models import PlatformRole, User

Locale = Literal["kk", "ru", "en"]
FullName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
Phone = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=32)]


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    full_name: str
    phone: str | None
    locale: Locale
    platform_role: PlatformRole
    email_verified: bool = Field(description="True once the email address has been verified.")
    created_at: datetime

    @classmethod
    def from_user(cls, user: User) -> "UserOut":
        return cls.model_validate(
            {
                "id": user.id,
                "email": user.email,
                "full_name": user.full_name,
                "phone": user.phone,
                "locale": user.locale,
                "platform_role": user.platform_role,
                "email_verified": user.email_verified_at is not None,
                "created_at": user.created_at,
            }
        )


class MeOut(UserOut):
    is_organizer: bool = Field(
        description="True once the user has an organizer profile (`POST /organizers/me`)."
    )

    @classmethod
    def from_user_and_role(cls, user: User, is_organizer: bool) -> "MeOut":
        return cls.model_validate(
            UserOut.from_user(user).model_dump() | {"is_organizer": is_organizer}
        )


class UpdateMeRequest(BaseModel):
    """Only the fields sent are changed. Email and password have their own flows."""

    full_name: FullName | None = None
    phone: Phone | None = Field(default=None, description="Send `null` to remove the phone.")
    locale: Locale | None = None

    @model_validator(mode="after")
    def _required_fields_not_null(self) -> "UpdateMeRequest":
        for field in ("full_name", "locale"):
            if field in self.model_fields_set and getattr(self, field) is None:
                raise ValueError(f"{field} cannot be null")
        return self
