import logging

from fastapi import APIRouter, Depends, BackgroundTasks
from redis.exceptions import LockError

from src.clients.redis_client import RedisClient
from src.dependencies.services import get_quiz_service, get_redis_client, get_quiz_generation_task
from src.schemas.generic import ApiResponse
from src.schemas.quiz import (
    CreateQuizRequest,
    QuizProgressResponse,
    CreateQuizAsyncResponse,
    QuizGenerationStatus,
)
from src.services.auth_service import AuthService
from src.services.quiz_service import QuizService
from src.services.task_service import QuizGenerationTask
from src.utils.exceptions import BadRequestException

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/quiz", tags=["Quiz"])


# @router.post(
#     "/create",
#     response_model=ApiResponse[List[Question]],
#     summary="Create Quiz Questions",
#     description="Generate quiz questions based on course context for the specified quiz.",
# )
# async def create_quiz(
#         request: CreateQuizRequest, quiz_service: QuizService = Depends(get_quiz_service),
#         user_id: str = Depends(AuthService.get_current_user)
# ) -> ApiResponse[List[Question]]:
#     """
#     Create quiz questions from course context.
#
#     - **prompt**: The prompt/query for generating quiz questions (e.g., "Tạo 10 câu hỏi về Chương 1")
#     - **skills**: List of skills to evaluate (e.g., ["phân tích", "lập trình"])
#     - **quiz_id**: UUID of the quiz lesson to generate questions for
#
#     Returns a list of questions with answers matching the database schema.
#     AI will automatically choose appropriate question types (SINGLE_CHOICE, MULTIPLE_CHOICE, TRUE_FALSE).
#     """
#     logger.info(
#         f"Received quiz creation request - Quiz ID: {request.quiz_id}, Prompt: {request.prompt[:50]}..."
#     )
#
#     # Generate quiz questions using injected service
#     questions_data = await quiz_service.generate_quiz(
#         prompt=request.prompt, quiz_id=request.quiz_id,
#         user_id=user_id
#     )
#
#     # Convert to response schema
#     questions = [
#         Question(
#             question_text=q["question_text"],
#             explanation=q.get("explanation"),
#             point=q.get("point", 1.0),
#             question_type=QuestionType(q["question_type"]),
#             answers=[
#                 Answer(answer_text=ans["answer_text"], is_correct=ans["is_correct"])
#                 for ans in q["answers"]
#             ],
#         )
#         for q in questions_data
#     ]
#
#     logger.info(f"Successfully generated {len(questions)} questions")
#
#     return ApiResponse[List[Question]].success(
#         data=questions, message=f"Successfully generated {len(questions)} questions"
#     )


@router.post(
    "/create",
    response_model=ApiResponse[CreateQuizAsyncResponse],
    summary="Create Quiz Questions Asynchronously",
    description="Start asynchronous quiz generation with Redis locking. Only one generation per quiz at a time.",
)
async def create_quiz_async(
        request: CreateQuizRequest,
        background_tasks: BackgroundTasks,
        quiz_service: QuizService = Depends(get_quiz_service),
        redis_client: RedisClient = Depends(get_redis_client),
        task_service: QuizGenerationTask = Depends(get_quiz_generation_task),
        user_id: str = Depends(AuthService.get_current_user),
) -> ApiResponse[CreateQuizAsyncResponse]:
    """
    Start async quiz generation with distributed locking.
    
    All validations (prompt, quiz existence, permissions) are performed SYNCHRONOUSLY
    before starting the background task. Only valid requests are queued.

    - **prompt**: The prompt/query for generating quiz questions
    - **quiz_id**: UUID of the quiz lesson to generate questions for

    Returns immediately with quiz_id for progress polling via /quiz/progress/{quiz_id}

    Raises:
        - 400 Bad Request: Invalid prompt, quiz not found, no permissions, or Redis unavailable
        - 409 Conflict: If quiz is already being generated (locked)
    """
    logger.info(
        f"Received async quiz creation request - Quiz ID: {request.quiz_id}, "
        f"Prompt: {request.prompt[:50]}..."
    )

    # Check if Redis is available
    if not redis_client.is_available():
        raise BadRequestException(
            "Redis is not available. Async quiz generation is disabled. "
            "Please use the synchronous endpoint /quiz/create instead."
        )

    logger.info(f"Running validation checks for quiz {request.quiz_id}...")
    await quiz_service.validate_quiz_request(
        prompt=request.prompt,
        quiz_id=request.quiz_id,
        user_id=user_id
    )
    logger.info(f"✓ All validation checks passed for quiz {request.quiz_id}")

    quiz_id_str = str(request.quiz_id)

    # Try to acquire lock (non-blocking)
    try:
        async with redis_client.acquire_quiz_lock(quiz_id_str):
            # Lock acquired, start background task
            logger.info(f"Lock acquired for quiz {request.quiz_id}, starting background task")

            # Add background task
            # Note: Validation already passed, so task will skip re-validation
            background_tasks.add_task(
                task_service.generate_quiz_async,
                quiz_service=quiz_service,
                prompt=request.prompt,
                quiz_id=request.quiz_id,
                user_id=user_id,
            )

            response_data = CreateQuizAsyncResponse(
                quiz_id=request.quiz_id,
                message=(
                    f"Bắt đầu tạo câu hỏi cho quiz {request.quiz_id}. "
                    f"Sử dụng endpoint /quiz/progress/{request.quiz_id} để theo dõi tiến độ."
                ),
            )

            return ApiResponse[CreateQuizAsyncResponse].success(
                data=response_data,
                message="Quiz generation started successfully"
            )

    except LockError:
        # Lock already held by another process
        logger.warning(f"Quiz {request.quiz_id} is already being generated")
        raise BadRequestException(
            f"Quiz {request.quiz_id} đang được tạo câu hỏi. "
            f"Vui lòng đợi hoặc kiểm tra tiến độ tại /quiz/progress/{request.quiz_id}"
        )


@router.get(
    "/progress/{quiz_id}",
    response_model=ApiResponse[QuizProgressResponse],
    summary="Get Quiz Generation Progress",
    description="Poll the progress of async quiz generation by quiz_id.",
)
async def get_quiz_progress(
        quiz_id: str,
        redis_client: RedisClient = Depends(get_redis_client),
) -> ApiResponse[QuizProgressResponse]:
    """
    Get the progress of quiz generation.

    - **quiz_id**: UUID of the quiz being generated

    Returns current status, progress percentage, and message.

    Status values:
        - PENDING: Task queued, not started yet
        - PROCESSING: Currently generating questions
        - COMPLETED: Successfully finished
        - FAILED: Error occurred

    Raises:
        - 404 Not Found: If no generation process found for this quiz_id
        - 503 Service Unavailable: If Redis is not available
    """
    logger.info(f"Checking progress for quiz {quiz_id}")

    # Check if Redis is available
    if not redis_client.is_available():
        raise BadRequestException(
            "Redis is not available. Progress tracking is disabled."
        )

    # Get progress from Redis
    progress_data = await redis_client.get_progress(quiz_id)

    if not progress_data:
        # No progress data found
        logger.warning(f"No progress data found for quiz {quiz_id}")
        raise BadRequestException(
            f"Không tìm thấy tiến độ tạo câu hỏi cho quiz {quiz_id}. "
            f"Quiz có thể chưa được bắt đầu hoặc dữ liệu đã hết hạn."
        )

    # Convert to response schema
    progress_response = QuizProgressResponse(
        status=QuizGenerationStatus(progress_data["status"]),
        progress=progress_data["progress"],
        message=progress_data["message"],
        total_questions=progress_data.get("total_questions", 0),
        error=progress_data.get("error"),
    )

    logger.info(
        f"Quiz {quiz_id} progress: {progress_response.status} - {progress_response.progress}%"
    )

    return ApiResponse[QuizProgressResponse].success(
        data=progress_response,
        message="Progress retrieved successfully"
    )
