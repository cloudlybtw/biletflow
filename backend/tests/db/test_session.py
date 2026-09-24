from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session


async def test_get_session_yields_async_session():
    generator = get_session()
    try:
        session = await generator.__anext__()
        assert isinstance(session, AsyncSession)
    finally:
        await generator.aclose()
