"""
Dependency injection functions for services.

Usage in endpoints:
    from fastapi import Depends
    from src.dependencies.services import get_quiz_service

    @router.post("/create")
    async def create_quiz(
        request: CreateQuizRequest,
        quiz_service: QuizService = Depends(get_quiz_service)
    ):
        return await quiz_service.generate_quiz(...)
"""

import logging
from functools import lru_cache

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import get_settings
from src.dependencies.db import get_database
from src.repositories.lesson_repo import LessonRepository
from src.repositories.quiz_repo import QuizRepository
from src.services.quiz_service import QuizService, RetrieverFactory, MCQGenerator

logger = logging.getLogger(__name__)


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


@lru_cache()
def get_mcq_generator() -> MCQGenerator:
    """
    Get singleton MCQGenerator instance.
    Uses Google Gemini for question generation with Pydantic parsing.
    """
    settings = get_settings()
    return MCQGenerator(settings)


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
        mcq_generator=get_mcq_generator(),
        quiz_repository=quiz_repository,
        lesson_repository=lesson_repository
    )
