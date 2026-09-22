from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import SERVICE_UNAVAILABLE, AppError
from app.db.session import get_session

router = APIRouter(tags=["health"])


@router.get("/health", summary="Health check")
async def health(session: AsyncSession = Depends(get_session)) -> dict:
    try:
        await session.execute(text("SELECT 1"))
    except Exception as exc:
        raise AppError(
            code=SERVICE_UNAVAILABLE,
            message="Database is unreachable.",
            status_code=503,
        ) from exc
    return {"status": "ok", "database": "ok"}
