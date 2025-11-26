"""
Repository dependency injection
"""
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession
from src.dependencies.db import get_db