import logging
from functools import lru_cache

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.clients.redis_client import RedisClient
from src.config import get_settings
from src.dependencies.db import get_database
from src.repositories.lesson_repo import LessonRepository
from src.repositories.quiz_repo import QuizRepository
from src.services.quiz_service import QuizService, RetrieverFactory
from src.services.task_service import QuizGenerationTask

logger = logging.getLogger(__name__)

# =============================
#   Redis Client (Singleton)
# =============================
_redis_client_instance = None


async def get_redis_client() -> RedisClient:
    """
    Get singleton RedisClient instance.
    Connection is established on first call and reused.
    """
    global _redis_client_instance

    if _redis_client_instance is None:
        settings = get_settings()
        _redis_client_instance = RedisClient(settings)
        await _redis_client_instance.connect()
        logger.info("RedisClient singleton created and connected")

    return _redis_client_instance


# =============================
#   Quiz Service Dependencies
# =============================
@lru_cache()
def get_retriever_factory() -> RetrieverFactory:
    """
    Get singleton RetrieverFactory instance.
    Creates hybrid retrievers (BM25 + Dense + RRF) for passages.
    """
    settings = get_settings()
    return RetrieverFactory(settings)


# =============================
#   Repository Dependencies
# =============================
async def get_quiz_repository(
        session: AsyncSession = Depends(get_database),
) -> QuizRepository:
    """
    Get QuizRepository instance with injected database session.
    """
    return QuizRepository(session)


async def get_lesson_repository(
        session: AsyncSession = Depends(get_database),
) -> LessonRepository:
    """
    Get LessonRepository instance with injected database session.
    """
    return LessonRepository(session)


# =============================
#   Quiz Service (Per-Request)
# =============================
async def get_quiz_service(
        quiz_repository: QuizRepository = Depends(get_quiz_repository),
        lesson_repository: LessonRepository = Depends(get_lesson_repository),
) -> QuizService:
    """
    Get QuizService instance with all dependencies injected.

    Note: This is NOT a singleton because it requires database session
    which is per-request. The retriever_factory and mcq_generator are
    still singletons (cached via @lru_cache).

    Dependencies:
        - RetrieverFactory: Creates hybrid retrievers per document
        - MCQGenerator: Generates questions via LLM
        - QuizRepository: Gets quiz by ID
        - LessonRepository: Gets lessons with course context
    """
    return QuizService(
        retriever_factory=get_retriever_factory(),
        quiz_repository=quiz_repository,
        lesson_repository=lesson_repository
    )


# =============================
#   Task Service Dependencies
# =============================
async def get_quiz_generation_task(
        redis_client: RedisClient = Depends(get_redis_client),
) -> QuizGenerationTask:
    """
    Get QuizGenerationTask instance with Redis client injected.

    Dependencies:
        - RedisClient: For progress tracking and locking
    """
    return QuizGenerationTask(redis_client=redis_client)
