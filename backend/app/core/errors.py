import logging
import math
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger(__name__)


class AppError(Exception):
    """Business error carrying the stable UPPER_SNAKE code clients translate."""

    def __init__(
        self,
        code: str,
        message: str,
        status_code: int = status.HTTP_400_BAD_REQUEST,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details
        super().__init__(message)


# Generic codes used by the framework-level handlers below. Domain codes
# (SOLD_OUT, PROMO_EXPIRED, ...) are added here as each module introduces them.
VALIDATION_ERROR = "VALIDATION_ERROR"
NOT_FOUND = "NOT_FOUND"
UNAUTHORIZED = "UNAUTHORIZED"
FORBIDDEN = "FORBIDDEN"
METHOD_NOT_ALLOWED = "METHOD_NOT_ALLOWED"
HTTP_ERROR = "HTTP_ERROR"
INTERNAL_SERVER_ERROR = "INTERNAL_SERVER_ERROR"
SERVICE_UNAVAILABLE = "SERVICE_UNAVAILABLE"

# auth
EMAIL_TAKEN = "EMAIL_TAKEN"
VERIFICATION_TOKEN_INVALID = "VERIFICATION_TOKEN_INVALID"
VERIFICATION_TOKEN_EXPIRED = "VERIFICATION_TOKEN_EXPIRED"
INVALID_CREDENTIALS = "INVALID_CREDENTIALS"
ACCOUNT_SUSPENDED = "ACCOUNT_SUSPENDED"
TOKEN_EXPIRED = "TOKEN_EXPIRED"
REFRESH_TOKEN_INVALID = "REFRESH_TOKEN_INVALID"
RESET_TOKEN_INVALID = "RESET_TOKEN_INVALID"
RESET_TOKEN_EXPIRED = "RESET_TOKEN_EXPIRED"
EMAIL_NOT_VERIFIED = "EMAIL_NOT_VERIFIED"

# organizers
ORGANIZER_PROFILE_EXISTS = "ORGANIZER_PROFILE_EXISTS"
ORGANIZER_PROFILE_NOT_FOUND = "ORGANIZER_PROFILE_NOT_FOUND"
PAYOUT_ACCOUNT_EXISTS = "PAYOUT_ACCOUNT_EXISTS"
PAYOUT_ACCOUNT_NOT_ACTIVE = "PAYOUT_ACCOUNT_NOT_ACTIVE"

# check-in
CHECKIN_NOT_REVERSIBLE = "CHECKIN_NOT_REVERSIBLE"

# refunds
ORDER_NOT_COMPLETED = "ORDER_NOT_COMPLETED"
ORDER_NOT_FREE = "ORDER_NOT_FREE"
ORDER_NOT_PAID = "ORDER_NOT_PAID"
REFUND_STATE_INVALID = "REFUND_STATE_INVALID"
EVENT_CANCELLATION_STATE_INVALID = "EVENT_CANCELLATION_STATE_INVALID"

# support
SUPPORT_ASSIGNEE_INVALID = "SUPPORT_ASSIGNEE_INVALID"
SUPPORT_CONTEXT_INVALID = "SUPPORT_CONTEXT_INVALID"

# reporting / administration
EXPORT_TOO_LARGE = "EXPORT_TOO_LARGE"
ADMIN_SELF_SUSPENSION = "ADMIN_SELF_SUSPENSION"
USER_STATE_INVALID = "USER_STATE_INVALID"

_STATUS_CODES = {
    status.HTTP_404_NOT_FOUND: NOT_FOUND,
    status.HTTP_401_UNAUTHORIZED: UNAUTHORIZED,
    status.HTTP_403_FORBIDDEN: FORBIDDEN,
    status.HTTP_405_METHOD_NOT_ALLOWED: METHOD_NOT_ALLOWED,
}


def _envelope(code: str, message: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"error": {"code": code, "message": message, "details": details or {}}}


def _finite_json(value):
    """Python's JSON parser accepts NaN/Infinity; error responses must remain JSON."""
    if isinstance(value, float) and not math.isfinite(value):
        return str(value)
    if isinstance(value, dict):
        return {key: _finite_json(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_finite_json(item) for item in value]
    return value


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=_envelope(exc.code, exc.message, exc.details),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            content=_envelope(
                VALIDATION_ERROR,
                "Request validation failed.",
                {"errors": _finite_json(jsonable_encoder(exc.errors()))},
            ),
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = _STATUS_CODES.get(exc.status_code, HTTP_ERROR)
        message = exc.detail if isinstance(exc.detail, str) else "HTTP error."
        return JSONResponse(status_code=exc.status_code, content=_envelope(code, message))

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled exception", exc_info=exc)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=_envelope(INTERNAL_SERVER_ERROR, "An unexpected error occurred."),
        )
