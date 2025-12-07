import logging
from typing import List

from fastapi import APIRouter, Depends

from src.dependencies.services import get_quiz_service
from src.schemas.generic import ApiResponse
from src.schemas.quiz import (
    CreateQuizRequest,
    Question,
    Answer,
    QuestionType,
)
from src.services.quiz_service import QuizService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/quiz", tags=["Quiz"])


@router.post(
    "/create",
    response_model=ApiResponse[List[Question]],
    summary="Create Quiz Questions",
    description="Generate quiz questions based on course context for the specified quiz."
)
async def create_quiz(
        request: CreateQuizRequest,
        quiz_service: QuizService = Depends(get_quiz_service)
) -> ApiResponse[List[Question]]:
    """
    Create quiz questions from course context.
    
    - **prompt**: The prompt/query for generating quiz questions (e.g., "Tạo 10 câu hỏi về Chương 1")
    - **skills**: List of skills to evaluate (e.g., ["phân tích", "lập trình"])
    - **quiz_id**: UUID of the quiz lesson to generate questions for
    
    Returns a list of questions with answers matching the database schema.
    AI will automatically choose appropriate question types (SINGLE_CHOICE, MULTIPLE_CHOICE, TRUE_FALSE).
    """
    logger.info(f"Received quiz creation request - Quiz ID: {request.quiz_id}, Prompt: {request.prompt[:50]}...")

    # Generate quiz questions using injected service
    questions_data = await quiz_service.generate_quiz(
        prompt=request.prompt,
        quiz_id=request.quiz_id
    )

    # Convert to response schema
    questions = [
        Question(
            question_text=q["question_text"],
            explanation=q.get("explanation"),
            point=q.get("point", 1.0),
            question_type=QuestionType(q["question_type"]),
            answers=[
                Answer(
                    answer_text=ans["answer_text"],
                    is_correct=ans["is_correct"]
                ) for ans in q["answers"]
            ]
        ) for q in questions_data
    ]

    logger.info(f"Successfully generated {len(questions)} questions")

    return ApiResponse[List[Question]].success(
        data=questions,
        message=f"Successfully generated {len(questions)} questions"
    )
