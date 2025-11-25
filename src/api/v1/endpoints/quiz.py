import logging
from typing import List

import requests
from fastapi import APIRouter, HTTPException

from src.api.v1.schemas import (
    CreateQuizRequest,
    CreateQuizResponse,
    Question,
    Answer,
    QuestionType,
)
from src.services.mcq_generator import QuizService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/quiz", tags=["Quiz"])


@router.post(
    "/create",
    response_model=CreateQuizResponse,
    summary="Create Quiz Questions",
    description="Generate quiz questions from a document based on the provided prompt and skills."
)
async def create_quiz(request: CreateQuizRequest) -> CreateQuizResponse:
    """
    Create quiz questions from a document.
    
    - **prompt**: The prompt/query for generating quiz questions (e.g., "Tạo 10 câu hỏi về Chương 1")
    - **skills**: List of skills to evaluate (e.g., ["phân tích", "lập trình"])
    - **document_url**: URL to the document (DOCX or PDF format supported)
    
    Returns a list of questions with answers matching the database schema.
    AI will automatically choose appropriate question types (SINGLE_CHOICE, MULTIPLE_CHOICE, TRUE_FALSE).
    """
    try:
        logger.info(f"Received quiz creation request - Prompt: {request.prompt[:50]}...")
        
        # Generate quiz questions
        questions_data = await QuizService.generate_quiz(
            prompt=request.prompt,
            skills=request.skills,
            document_url=request.document_url
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
        
        return CreateQuizResponse(
            success=True,
            message=f"Successfully generated {len(questions)} questions",
            data=questions
        )
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to fetch document: {e}")
        raise HTTPException(
            status_code=400,
            detail=f"Failed to fetch document from URL: {str(e)}"
        )
    except ValueError as e:
        logger.error(f"Document processing error: {e}")
        raise HTTPException(
            status_code=400,
            detail=f"Document processing error: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Quiz generation failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Quiz generation failed: {str(e)}"
        )
