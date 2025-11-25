import logging
from typing import List, Optional
from enum import Enum

from langchain_google_genai import GoogleGenerativeAI
from langchain_core.output_parsers import PydanticOutputParser
from pydantic import BaseModel, Field

from src.config import get_settings
from src.data.dataloader import load_document_to_dataframe
from src.retriever.passages import PassageBuilder
from src.retriever.bm25_retrieval import BM25Retriever
from src.retriever.dense_retrieval import DenseRetriever
from src.retriever.fusion import RRFFusion

logger = logging.getLogger(__name__)
settings = get_settings()


# =============================
#   Enums
# =============================
class QuestionType(str, Enum):
    """Question type enum matching Java QuestionType"""
    SINGLE_CHOICE = "SINGLE_CHOICE"
    MULTIPLE_CHOICE = "MULTIPLE_CHOICE"
    TRUE_FALSE = "TRUE_FALSE"


# =============================
#   Internal Pydantic Models for LLM Parsing
# =============================
class AnswerInternal(BaseModel):
    """Internal model for answer - matching Answer entity structure"""
    answer_text: str = Field(..., description="Nội dung câu trả lời")
    is_correct: bool = Field(..., description="True nếu đây là đáp án đúng, False nếu sai")


class QuestionInternal(BaseModel):
    """Internal model for question - matching Question entity structure"""
    question_text: str = Field(..., description="Nội dung câu hỏi")
    explanation: Optional[str] = Field(None, description="Giải thích cho đáp án đúng")
    point: float = Field(default=1.0, description="Điểm số cho câu hỏi")
    question_type: QuestionType = Field(
        default=QuestionType.SINGLE_CHOICE,  
        description="Loại câu hỏi: SINGLE_CHOICE, MULTIPLE_CHOICE, hoặc TRUE_FALSE"
    )
    answers: List[AnswerInternal] = Field(..., description="Danh sách các câu trả lời")


class QuizOutputInternal(BaseModel):
    """Internal model for quiz output from LLM"""
    data: List[QuestionInternal]


# =============================
#   Retriever Pipeline
# =============================
class RetrieverPipeline:
    """Combines BM25, Dense, and Fusion retrieval"""

    def __init__(self, passages, rrf_k: int = None):
        self.passages = passages
        rrf_k = rrf_k or settings.rrf_k
        self.bm25 = BM25Retriever(passages)
        self.dense = DenseRetriever(passages, openai_api_key=settings.openai_api_key)
        self.fusion = RRFFusion(self.bm25, self.dense, rrf_k=rrf_k)

    def retrieve(self, query: str, top_k: int = None) -> List[str]:
        top_k = top_k or settings.candidates_n
        results = self.fusion.fuse(query, top_k=top_k)
        logger.debug(f"Retrieved {len(results)} candidates for query: {query[:50]}...")
        candidate_texts = [text for _, text in results]
        return candidate_texts


# =============================
#   MCQ Generator
# =============================
class MCQGenerator:
    """Generate MCQ questions from context using LLM"""

    def __init__(self, model_name: str = None, api_key: str = None):
        model_name = model_name or settings.gemini_model_name
        api_key = api_key or settings.google_api_key
        self.llm = GoogleGenerativeAI(model=model_name, google_api_key=api_key)
        self.parser = PydanticOutputParser(pydantic_object=QuizOutputInternal)
        self.format_instructions = self.parser.get_format_instructions()

    def generate(self, context: str, query: str, skill: str) -> QuizOutputInternal:
        prompt = f"""
        Bạn là Giảng viên có học vị Tiến sĩ, chuyên gia tạo các bộ câu hỏi để kiểm tra kiến thức của sinh viên.
        
        YÊU CẦU TẠO CÂU HỎI:
        {query}
        
        QUY TẮC:
        - Số lượng câu hỏi tạo ra phải đảm bảo bằng đúng số lượng câu hỏi mà tôi yêu cầu
        - Hãy tự chọn loại câu hỏi phù hợp nhất cho từng câu, có thể kết hợp nhiều loại để tạo sự đa dạng:
            + SINGLE_CHOICE: Câu hỏi trắc nghiệm một đáp án đúng (4 lựa chọn, chỉ 1 đáp án đúng)
            + MULTIPLE_CHOICE: Câu hỏi trắc nghiệm nhiều đáp án đúng (4 lựa chọn, có thể có nhiều đáp án đúng)
            + TRUE_FALSE: Câu hỏi Đúng/Sai (chỉ có 2 lựa chọn: "Đúng" và "Sai")
        - Mỗi câu hỏi PHẢI CÓ phần giải thích (explanation) cho đáp án đúng
        - Điểm mặc định cho mỗi câu hỏi là 1.0
        - Với mỗi câu trả lời, is_correct = true nếu đúng, is_correct = false nếu sai
        
        KIẾN THỨC LIÊN QUAN: {skill}
        
        NỘI DUNG BÀI HỌC:
        {context}

        {self.format_instructions}
        """

        logger.info("Generating quiz questions via LLM...")
        raw_output = self.llm.invoke(prompt)
        logger.debug("LLM response received, parsing output...")
        parsed_output: QuizOutputInternal = self.parser.parse(raw_output)

        return parsed_output


# =============================
#   Quiz Service
# =============================
class QuizService:
    """Service for quiz generation operations"""

    @staticmethod
    async def generate_quiz(
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
            List of Question objects matching the database schema
        """
        logger.info(f"Starting quiz generation for prompt: {prompt[:50]}...")

        # 1. Load document
        context = ""
        if document_url:
            logger.info(f"Loading document from: {document_url}")
            df = load_document_to_dataframe(document_url)
            passages = PassageBuilder.build_passages_from_records(df)
            logger.info(f"Loaded {len(passages)} passages from document")
            # 2. Retrieve relevant passages
            logger.info("Retrieving relevant passages...")
            retriever = RetrieverPipeline(passages)
            candidates = retriever.retrieve(prompt)
            context = "\n".join(candidates)
            logger.info(f"Retrieved {len(candidates)} candidate passages")

        # 3. Generate questions
        mcq_gen = MCQGenerator()
        quiz_output = mcq_gen.generate(
            context=context,
            query=prompt,
            skill=", ".join(skills)
        )

        # 4. Convert to dict format matching database schema
        questions_dict = quiz_output.model_dump()

        logger.info(f"Generated {len(questions_dict['data'])} questions")
        return questions_dict["data"]
