from enum import Enum
from typing import Optional, List

from pydantic import BaseModel, Field


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
    is_correct: bool = Field(
        ..., description="True nếu đây là đáp án đúng, False nếu sai"
    )


class QuestionInternal(BaseModel):
    """Internal model for question - matching Question entity structure"""

    question_text: str = Field(..., description="Nội dung câu hỏi")
    explanation: Optional[str] = Field(None, description="Giải thích cho đáp án đúng")
    point: float = Field(default=1.0, description="Điểm số cho câu hỏi")
    question_type: QuestionType = Field(
        default=QuestionType.SINGLE_CHOICE,
        description="Loại câu hỏi: SINGLE_CHOICE, MULTIPLE_CHOICE, hoặc TRUE_FALSE",
    )
    answers: List[AnswerInternal] = Field(..., description="Danh sách các câu trả lời")


class QuizOutputInternal(BaseModel):
    """Internal model for quiz output from LLM"""

    data: List[QuestionInternal]
