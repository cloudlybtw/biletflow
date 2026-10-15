from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.pagination import Pagination


async def read_page(session: AsyncSession, query, page: Pagination):
    total = await session.scalar(select(func.count()).select_from(query.order_by(None).subquery()))
    rows = await session.scalars(query.limit(page.limit).offset(page.offset))
    return list(rows.all()), total or 0
