"""
Quiz Service - Generates MCQ questions from documents using Hybrid RAG.

Architecture:
    - QuizRepository: Gets quiz by ID (Lesson with type QUIZ)
    - LessonRepository: Gets lessons with course context
    - RetrieverFactory: Creates hybrid retriever (BM25 + Dense + RRF)
    - MCQGenerator: LLM-based question generation with Pydantic parsing
    - QuizService: Orchestrates the pipeline (injectable via FastAPI Depends)
"""

import logging
import uuid
from typing import List, Optional
from uuid import UUID

from langchain_core.output_parsers import PydanticOutputParser

from src.config import Settings
from src.factory.LLMFactory import LLMFactory
from src.model import Lesson
from src.repositories.lesson_repo import LessonRepository
from src.repositories.quiz_repo import QuizRepository
from src.retriever.bm25_retrieval import BM25Retriever
from src.retriever.dense_retrieval import DenseRetriever
from src.retriever.fusion import RRFFusion
from src.schemas.external.quiz_llm import QuizOutputInternal
from src.services.prompt_service import PromptService
from src.utils.exceptions import (
    AccessDeniedException,
    UnauthorizedException,
    BadRequestException,
    ResourceNotFoundException,
)
from src.utils.parser_utils import ParserUtils

logger = logging.getLogger(__name__)


# =============================
#   Retriever Factory
# =============================
class RetrieverFactory:
    """Factory for creating hybrid retrievers"""

    def __init__(self, settings: Settings):
        self._settings = settings

    def create(self, passages: List[dict]) -> "HybridRetriever":
        """
        Create a hybrid retriever for the given passages.

        Args:
            passages: List of passage dicts with "id" and "content" keys

        Returns:
            HybridRetriever instance configured with BM25 + Dense + RRF
        """
        return HybridRetriever(
            passages=passages,
            openai_api_key=self._settings.openai_api_key,
            rrf_k=self._settings.rrf_k,
            candidates_n=self._settings.candidates_n,
        )


class HybridRetriever:
    """Combines BM25, Dense, and RRF Fusion retrieval"""

    def __init__(
            self,
            passages: List[dict],
            openai_api_key: str,
            rrf_k: int = 60,
            candidates_n: int = 20,
    ):
        self._passages = passages
        self._candidates_n = candidates_n
        self._bm25 = BM25Retriever(passages)
        self._dense = DenseRetriever(passages, openai_api_key=openai_api_key)
        self._fusion = RRFFusion(self._bm25, self._dense, rrf_k=rrf_k)

    def retrieve(self, query: str, top_k: int = None) -> List[str]:
        """
        Retrieve relevant passages using hybrid search.

        Args:
            query: Search query
            top_k: Number of results to return (defaults to candidates_n)

        Returns:
            List of passage texts
        """
        top_k = top_k or self._candidates_n
        results = self._fusion.fuse(query, top_k=top_k)
        logger.debug(f"Retrieved {len(results)} candidates for query: {query[:50]}...")
        return [text for _, text in results]


# =============================
#   Quiz Service
# =============================
class QuizService:
    """
    Service for quiz generation operations.

    Orchestrates quiz retrieval, course context loading, and question generation pipeline.
    Inject via FastAPI Depends() for proper dependency management.

    Example:
        @router.post("/create")
        async def create_quiz(
            request: CreateQuizRequest,
            quiz_service: QuizService = Depends(get_quiz_service)
        ):
            return await quiz_service.generate_quiz(...)
    """
    # Higher token limit for quiz generation (each question ~200-300 tokens)
    QUIZ_MAX_TOKENS = 4096

    def __init__(
            self,
            retriever_factory: RetrieverFactory,
            quiz_repository: QuizRepository,
            lesson_repository: LessonRepository,
    ):
        self._retriever_factory = retriever_factory
        self._quiz_repository = quiz_repository
        self._lesson_repository = lesson_repository
        self._llm = LLMFactory.create(max_tokens=QuizService.QUIZ_MAX_TOKENS, streaming=False)

    async def validate_quiz_request(self, prompt: str, quiz_id: UUID, user_id: str) -> Lesson:
        """
        Validate quiz generation request synchronously.
        
        Performs all validation checks that should fail fast:
        - Prompt validation (length, content)
        - Quiz existence check
        - User permission check
        - Section availability check
        
        This method is called BEFORE starting async task to ensure
        invalid requests fail immediately with proper error messages.

        Args:
            prompt: The prompt/query for generating quiz questions
            quiz_id: UUID of the quiz lesson
            user_id: ID of the user requesting quiz generation

        Raises:
            BadRequestException: Invalid prompt or quiz configuration
            UnauthorizedException: Invalid user ID format
            AccessDeniedException: User lacks permission
            ResourceNotFoundException: Quiz not found
        """
        # 1. Validate prompt
        self._validate_prompt(prompt)

        # 2. Get the quiz by ID
        quiz = await self._quiz_repository.get_quiz_by_id(quiz_id)
        if not quiz:
            raise ResourceNotFoundException(f"Quiz not found with ID: {quiz_id}")

        logger.info(f"Found quiz: {quiz.title}")

        # 3. Check user has permission to modify the quiz
        try:
            user_uuid = uuid.UUID(user_id)
        except ValueError:
            raise UnauthorizedException("Invalid user ID format")

        is_instructor = await self._lesson_repository.is_instructor(quiz.id, user_uuid)
        if not is_instructor:
            raise AccessDeniedException(
                "User does not have permission to modify this quiz"
            )

        # 4. Verify quiz has associated section
        if not quiz.section_id:
            raise BadRequestException(f"Quiz {quiz_id} has no associated section")

        logger.info(f"✓ All validation checks passed for quiz {quiz_id}")
        return quiz

    async def generate_quiz(self, prompt: str, quiz_id: UUID, user_id: str) -> List[dict]:
        """
        Generate quiz questions based on course context and save them to the database.

        Args:
            prompt: The prompt/query for generating quiz questions
            quiz_id: UUID of the quiz lesson
            user_id: ID of the user requesting quiz generation

        Returns:
            List of Question dicts matching the API schema

        Raises:
            ValueError: If quiz not found or has no section
        """
        logger.info(
            f"Starting quiz generation for quiz_id: {quiz_id}, prompt: {prompt[:50]}..."
        )

        # 0. Validate prompt early
        quiz = await self.validate_quiz_request(prompt, quiz_id, user_id)

        lessons_context = await self._lesson_repository.get_lessons_with_course_context(
            quiz.section_id
        )

        # 3. Build context string from course information
        context = PromptService.build_course_context(list(lessons_context), quiz)
        logger.info(f"Built course context with {len(lessons_context)} lessons")

        # 3.1 Get existing questions in the quiz to avoid duplicates
        existing_questions = await self._get_existing_questions(quiz_id)
        if existing_questions:
            logger.info(
                f"Found {len(existing_questions)} existing questions in quiz"
            )

        # 4. Generate questions via LLM
        parser = PydanticOutputParser(pydantic_object=QuizOutputInternal)
        prompt = PromptService.build_quiz_creating_prompt(
            context, prompt, parser.get_format_instructions(), existing_questions
        )

        logger.info("Generating quiz questions via LLM...")
        raw_output = self._llm.invoke(prompt)
        logger.debug("LLM response received, parsing output...")

        # Extract content if output is an AIMessage (ChatModel)
        content = (
            raw_output.content if hasattr(raw_output, "content") else str(raw_output)
        )
        logger.debug(f"Raw LLM output: {content[:500]}...")
        # Try to parse with retry logic
        quiz_output = ParserUtils.parse_with_fallback(content, parser, QuizOutputInternal)

        # 5. Convert to dict format matching API schema
        questions_dict = quiz_output.model_dump()
        questions_data = questions_dict["data"]
        logger.info(f"Generated {len(questions_data)} questions")

        # 6. Save questions to database
        await self._quiz_repository.add_questions_to_quiz(
            lesson_id=quiz_id, questions_data=questions_data
        )
        await self._quiz_repository.commit()
        logger.info(f"Saved {len(questions_data)} questions to quiz {quiz_id}")

        return questions_data

    async def _get_existing_questions(self, quiz_id: UUID) -> Optional[List[dict]]:
        """
        Get existing questions in a quiz for context.

        Args:
            quiz_id: UUID of the quiz lesson

        Returns:
            List of question dicts with question_text, question_type, and answers,
            or None if no existing questions
        """
        quiz_details = await self._quiz_repository.get_quiz_details_by_lesson_id(
            quiz_id
        )

        if not quiz_details or not quiz_details.questions:
            return None

        existing_questions = []
        for question in quiz_details.questions:
            question_dict = {
                "question_text": question.question_text,
                "question_type": question.question_type,
                "answers": [
                    {
                        "answer_text": answer.answer_text,
                        "is_correct": answer.is_correct,
                    }
                    for answer in question.answers
                ],
            }
            existing_questions.append(question_dict)

        return existing_questions if existing_questions else None

    @staticmethod
    def _validate_prompt(prompt: str) -> None:
        """
        Validate the prompt for quiz generation.

        Args:
            prompt: The user's prompt for generating quiz questions

        Raises:
            BadRequestException: If the prompt is invalid or incompatible
        """
        if not prompt:
            raise BadRequestException("Prompt cannot be empty")

        prompt_stripped = prompt.strip()

        if len(prompt_stripped) < 10:
            raise BadRequestException(
                "Prompt is too short. Please provide a more detailed request."
            )

        if len(prompt_stripped) > 2000:
            raise BadRequestException(
                "Prompt is too long. Please keep it under 2000 characters."
            )

        # Check for minimum meaningful content (at least some Vietnamese or English words)
        # Remove special characters and check remaining content
        import re

        meaningful_content = re.sub(r"[^\w\sàáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹđ]", "",
                                    prompt_stripped, flags=re.IGNORECASE)
        words = meaningful_content.split()

        if len(words) < 2:
            raise BadRequestException(
                "Prompt must contain meaningful content. "
                "Please specify what kind of questions you want to generate."
            )

        # Check for number of questions (optional validation)
        # Try to extract number from prompt to warn if too many requested
        number_match = re.search(r"(\d+)\s*(câu|question|questions)", prompt_stripped, re.IGNORECASE)
        if number_match:
            num_questions = int(number_match.group(1))
            if num_questions > 20:
                raise BadRequestException(
                    f"Cannot generate more than 20 questions at once. "
                    f"You requested {num_questions} questions."
                )
            if num_questions < 1:
                raise BadRequestException(
                    "Number of questions must be at least 1."
                )
