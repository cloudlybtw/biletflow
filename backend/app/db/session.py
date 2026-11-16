from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.db.connection import connection_options

settings = get_settings()

database_url, connect_args = connection_options(
    settings.database_url, settings.database_ssl_mode, settings.database_ssl_ca_file
)
engine = create_async_engine(database_url, connect_args=connect_args, pool_pre_ping=True)

AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session
