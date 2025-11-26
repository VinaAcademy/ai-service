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
from functools import lru_cache
import logging

from src.config import get_settings, Settings
from src.services.langchain_service import LangChainService
from src.services.quiz_service import (
    QuizService,
    DocumentLoader,
    RetrieverFactory,
    MCQGenerator
)

logger = logging.getLogger(__name__)


# =============================
#   LangChain Service (Singleton)
# =============================
@lru_cache()
def get_langchain_service() -> LangChainService:
    """
    Get singleton LangChainService instance.
    """
    return LangChainService()


# =============================
#   Quiz Service Dependencies
# =============================
@lru_cache()
def get_document_loader() -> DocumentLoader:
    """
    Get singleton DocumentLoader instance.
    Handles DOCX/PDF loading and passage extraction.
    """
    return DocumentLoader()


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


@lru_cache()
def get_quiz_service() -> QuizService:
    """
    Get singleton QuizService instance with all dependencies injected.
    
    Dependencies:
        - DocumentLoader: Loads documents from URL
        - RetrieverFactory: Creates hybrid retrievers per document
        - MCQGenerator: Generates questions via LLM
    """
    return QuizService(
        document_loader=get_document_loader(),
        retriever_factory=get_retriever_factory(),
        mcq_generator=get_mcq_generator()
    )
