"""
Quiz Service - Generates MCQ questions from documents using Hybrid RAG.

Architecture:
    - DocumentLoader: Loads DOCX/PDF → DataFrame
    - RetrieverFactory: Creates hybrid retriever (BM25 + Dense + RRF)
    - MCQGenerator: LLM-based question generation with Pydantic parsing
    - QuizService: Orchestrates the pipeline (injectable via FastAPI Depends)
"""
import json
import logging
import re
from typing import List

from langchain_core.output_parsers import PydanticOutputParser
from pydantic import ValidationError

from src.config import Settings
from src.factory.LLMFactory import LLMFactory
from src.retriever.bm25_retrieval import BM25Retriever
from src.retriever.dense_retrieval import DenseRetriever
from src.retriever.fusion import RRFFusion
from src.schemas.external.quiz_llm import QuizOutputInternal
from src.services.prompt_service import PromptService
from src.utils.document_utils import DocumentUtils

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
            candidates_n=self._settings.candidates_n
        )


class HybridRetriever:
    """Combines BM25, Dense, and RRF Fusion retrieval"""

    def __init__(
            self,
            passages: List[dict],
            openai_api_key: str,
            rrf_k: int = 60,
            candidates_n: int = 20
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
#   MCQ Generator
# =============================
class MCQGenerator:
    """Generate MCQ questions from context using LLM"""

    # Higher token limit for quiz generation (each question ~200-300 tokens)
    QUIZ_MAX_TOKENS = 4096

    def __init__(self, settings: Settings):
        self._settings = settings
        # Use higher max_tokens for quiz generation, disable streaming for structured output
        self._llm = LLMFactory.create(
            max_tokens=self.QUIZ_MAX_TOKENS,
            streaming=False
        )
        self._parser = PydanticOutputParser(pydantic_object=QuizOutputInternal)
        self._format_instructions = self._parser.get_format_instructions()

    def generate(self, context: str, query: str, skills: str) -> QuizOutputInternal:
        """
        Generate quiz questions from context.
        
        Args:
            context: Document content to generate questions from
            query: User's prompt specifying what questions to generate
            skills: Skills to evaluate
            
        Returns:
            QuizOutputInternal with parsed questions
        """
        prompt = PromptService.build_quiz_creating_prompt(context, query, skills, self._format_instructions)

        logger.info("Generating quiz questions via LLM...")
        raw_output = self._llm.invoke(prompt)
        logger.debug("LLM response received, parsing output...")

        # Extract content if output is an AIMessage (ChatModel)
        content = raw_output.content if hasattr(raw_output, "content") else str(raw_output)

        logger.debug(f"Raw LLM output: {content[:500]}...")

        # Try to parse with retry logic
        return self._parse_with_fallback(content)

    def _parse_with_fallback(self, content: str) -> QuizOutputInternal:
        """
        Parse LLM output with fallback strategies.
        
        Args:
            content: Raw LLM output string
            
        Returns:
            QuizOutputInternal with parsed questions
            
        Raises:
            ValueError: If parsing fails after all attempts
        """
        # Check for truncated response
        if MCQGenerator._is_truncated(content):
            logger.error("LLM response appears to be truncated (incomplete JSON)")
            raise ValueError(
                "LLM response was truncated. Try requesting fewer questions or increase max_tokens."
            )

        # Strategy 1: Direct parsing
        try:
            return self._parser.parse(content)
        except (ValidationError, Exception) as e:
            logger.warning(f"Direct parsing failed: {e}")

        # Strategy 2: Extract JSON from markdown code block
        try:
            json_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', content)
            if json_match:
                json_str = json_match.group(1)
                return self._parser.parse(json_str)
        except (ValidationError, Exception) as e:
            logger.warning(f"Markdown extraction failed: {e}")

        # Strategy 3: Find JSON object directly
        try:
            json_match = re.search(r'\{[\s\S]*}', content)
            if json_match:
                json_str = json_match.group(0)
                data = json.loads(json_str)
                return QuizOutputInternal.model_validate(data)
        except (ValidationError, json.JSONDecodeError, Exception) as e:
            logger.warning(f"JSON extraction failed: {e}")

        # Strategy 4: Try to fix common issues and parse
        try:
            # Remove any leading/trailing non-JSON content
            cleaned = content.strip()
            if cleaned.startswith('```'):
                cleaned = re.sub(r'^```\w*\n?', '', cleaned)
                cleaned = re.sub(r'\n?```$', '', cleaned)

            data = json.loads(cleaned)
            return QuizOutputInternal.model_validate(data)
        except (ValidationError, json.JSONDecodeError, Exception) as e:
            logger.error(f"All parsing strategies failed. Last error: {e}")
            logger.debug(f"Raw content was: {content[:500]}...")
            raise ValueError(f"Failed to parse LLM output: {e}")

    @staticmethod
    def _is_truncated(content: str) -> bool:
        """
        Check if the LLM response appears to be truncated.

        Args:
            content: Raw LLM output string

        Returns:
            True if response appears truncated
        """
        content = content.strip()

        # Check if JSON is properly closed
        open_braces = content.count('{')
        close_braces = content.count('}')
        open_brackets = content.count('[')
        close_brackets = content.count(']')

        if open_braces != close_braces or open_brackets != close_brackets:
            logger.warning(
                f"Unbalanced JSON: {{ {open_braces}/{close_braces} }}, [ {open_brackets}/{close_brackets} ]"
            )
            return True

        # Check for common truncation patterns
        truncation_patterns = [
            r'"answer_text":\s*"[^"]*$',  # Truncated in middle of answer_text
            r'"question_text":\s*"[^"]*$',  # Truncated in middle of question_text
            r'"explanation":\s*"[^"]*$',  # Truncated in middle of explanation
            r',\s*$',  # Ends with comma
            r':\s*$',  # Ends with colon
        ]

        for pattern in truncation_patterns:
            if re.search(pattern, content):
                logger.warning(f"Truncation pattern detected: {pattern}")
                return True

        return False


# =============================
#   Quiz Service
# =============================
class QuizService:
    """
    Service for quiz generation operations.
    
    Orchestrates the document loading, retrieval, and question generation pipeline.
    Inject via FastAPI Depends() for proper dependency management.
    
    Example:
        @router.post("/create")
        async def create_quiz(
            request: CreateQuizRequest,
            quiz_service: QuizService = Depends(get_quiz_service)
        ):
            return await quiz_service.generate_quiz(...)
    """

    def __init__(
            self,
            retriever_factory: RetrieverFactory,
            mcq_generator: MCQGenerator
    ):
        self._retriever_factory = retriever_factory
        self._mcq_generator = mcq_generator

    async def generate_quiz(
            self,
            prompt: str,
            skills: List[str],
            document_url: str
    ) -> List[dict]:
        """
        Generate quiz questions from a document.
        
        Args:
            prompt: The prompt/query for generating quiz questions
            skills: List of skills to evaluate
            document_url: URL to the document (DOCX or PDF)
            
        Returns:
            List of Question dicts matching the API schema
        """
        logger.info(f"Starting quiz generation for prompt: {prompt[:50]}...")

        # 1. Load document and build passages
        context = ""
        if document_url:
            passages = DocumentUtils.convert_document_to_passages(document_url)

            # 2. Retrieve relevant passages using hybrid search
            if passages:
                logger.info("Retrieving relevant passages...")
                retriever = self._retriever_factory.create(passages)
                candidates = retriever.retrieve(prompt)
                context = "\n".join(candidates)
                logger.info(f"Retrieved {len(candidates)} candidate passages")

        # 3. Generate questions via LLM
        quiz_output = self._mcq_generator.generate(context=context, query=prompt, skills=", ".join(skills))

        # 4. Convert to dict format matching API schema
        questions_dict = quiz_output.model_dump()
        logger.info(f"Generated {len(questions_dict['data'])} questions")

        return questions_dict["data"]
