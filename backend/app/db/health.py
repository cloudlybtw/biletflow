from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import SERVICE_UNAVAILABLE, AppError


async def check_database(session: AsyncSession) -> None:
    try:
        await session.execute(text("SELECT 1"))
    except Exception as exc:
        raise AppError(
            code=SERVICE_UNAVAILABLE,
            message="Database is unreachable.",
            status_code=503,
        ) from exc
