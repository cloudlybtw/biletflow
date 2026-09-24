from collections.abc import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.main import create_app


class _BrokenSession:
    async def execute(self, *args, **kwargs):
        raise ConnectionError("could not connect to server")


@pytest.fixture
async def unreachable_db_client() -> AsyncGenerator[AsyncClient, None]:
    app = create_app()

    async def _get_broken_session() -> AsyncGenerator[AsyncSession, None]:
        yield _BrokenSession()

    app.dependency_overrides[get_session] = _get_broken_session

    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


async def test_health_returns_503_when_db_unreachable(unreachable_db_client: AsyncClient):
    response = await unreachable_db_client.get("/api/v1/health")

    assert response.status_code == 503
    assert response.json() == {
        "error": {
            "code": "SERVICE_UNAVAILABLE",
            "message": "Database is unreachable.",
            "details": {},
        }
    }


async def test_health_ok_when_db_reachable(client: AsyncClient):
    response = await client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok"}
