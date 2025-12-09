from enum import Enum
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


# =============================
#   Enums
# =============================
class QuestionType(str, Enum):
    """Enum for question types matching Java QuestionType"""

    SINGLE_CHOICE = "SINGLE_CHOICE"
    MULTIPLE_CHOICE = "MULTIPLE_CHOICE"
    TRUE_FALSE = "TRUE_FALSE"


# =============================
#   Request Schemas
# =============================
class CreateQuizRequest(BaseModel):
    """Request schema for creating a quiz"""

    prompt: str = Field(
        ..., description="The prompt/query for generating quiz questions"
    )
    quiz_id: UUID = Field(
        ..., description="UUID of the quiz lesson to generate questions for"
    )


# =============================
#   Response Schemas
# =============================
class Answer(BaseModel):
    """Schema for a single answer option - matching Answer entity"""

    answer_text: str = Field(..., description="The text content of the answer")
    is_correct: bool = Field(..., description="Whether this answer is correct")


class Question(BaseModel):
    """Schema for a single question - matching Question entity"""

    question_text: str = Field(..., description="The question text")
    explanation: Optional[str] = Field(
        None, description="Explanation for the correct answer"
    )
    point: float = Field(default=1.0, description="Point value for the question")
    question_type: QuestionType = Field(
        default=QuestionType.SINGLE_CHOICE, description="Type of question"
    )
    answers: List[Answer] = Field(..., description="List of possible answers")
