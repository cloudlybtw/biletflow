import pytest
from fastapi import FastAPI, HTTPException
from httpx import ASGITransport, AsyncClient
from pydantic import BaseModel

from app.core.errors import AppError, register_exception_handlers


class _Body(BaseModel):
    name: str


def _build_app() -> FastAPI:
    app = FastAPI()
    register_exception_handlers(app)

    @app.get("/app-error")
    async def raise_app_error() -> None:
        raise AppError(
            code="SOLD_OUT",
            message="No tickets left.",
            status_code=409,
            details={"ticket_type_id": "abc"},
        )

    @app.get("/not-found")
    async def raise_not_found() -> None:
        raise HTTPException(status_code=404, detail="Order not found.")

    @app.post("/validate")
    async def validate(body: _Body) -> dict:
        return {"name": body.name}

    @app.get("/boom")
    async def raise_unhandled() -> None:
        raise ValueError("something broke")

    return app


@pytest.fixture
async def client():
    # raise_app_exceptions=False: Starlette's ServerErrorMiddleware re-raises
    # after our handler already sent the response (so a real ASGI server can
    # log it); a real HTTP client only ever sees that response, so the test
    # transport should too.
    transport = ASGITransport(app=_build_app(), raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


async def test_app_error_uses_envelope(client):
    response = await client.get("/app-error")

    assert response.status_code == 409
    assert response.json() == {
        "error": {
            "code": "SOLD_OUT",
            "message": "No tickets left.",
            "details": {"ticket_type_id": "abc"},
        }
    }


async def test_http_exception_uses_envelope(client):
    response = await client.get("/not-found")

    assert response.status_code == 404
    assert response.json() == {
        "error": {"code": "NOT_FOUND", "message": "Order not found.", "details": {}}
    }


async def test_validation_error_returns_422_envelope(client):
    response = await client.post("/validate", json={})

    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert body["error"]["details"]["errors"]


async def test_unhandled_exception_returns_500_envelope(client):
    response = await client.get("/boom")

    assert response.status_code == 500
    assert response.json() == {
        "error": {
            "code": "INTERNAL_SERVER_ERROR",
            "message": "An unexpected error occurred.",
            "details": {},
        }
    }
