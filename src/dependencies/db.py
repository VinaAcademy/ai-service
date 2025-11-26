from typing import Any, AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession
from src.db.session import get_db


async def get_database() -> AsyncGenerator[AsyncSession | Any, Any]:
    """
    Dependency để inject database session vào endpoints
    """
    async for session in get_db():
        yield session

