from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.health import check_database
from app.db.session import get_session

router = APIRouter(tags=["health"])


class HealthOut(BaseModel):
    status: Literal["ok"] = "ok"
    database: Literal["ok"] = "ok"


@router.get("/health", summary="Health check", response_model=HealthOut)
async def health(session: AsyncSession = Depends(get_session)) -> HealthOut:
    await check_database(session)
    return HealthOut()
