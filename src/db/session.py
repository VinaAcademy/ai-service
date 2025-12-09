from typing import Any, AsyncGenerator

from sqlalchemy import NullPool
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from src.config import get_settings
from src.db.base import Base

settings = get_settings()
engine = create_async_engine(
    settings.database_url,
    echo=True if settings.environment == "development" else False,
    poolclass=NullPool,
)
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def get_db() -> AsyncGenerator[AsyncSession | Any, Any]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_db():
    async with engine.begin() as conn:
        if settings.environment == "development":
            await conn.run_sync(Base.metadata.create_all)


async def close_db():
    await engine.dispose()
