"""
Background task service for asynchronous quiz generation.

Features:
    - Async task execution with progress tracking
    - Error handling and recovery
    - Integration with Redis for distributed locking
"""

import asyncio
import logging
from uuid import UUID

from src.clients.redis_client import RedisClient
from src.services.quiz_service import QuizService
from src.utils.exceptions import (
    AccessDeniedException,
    UnauthorizedException,
    BadRequestException,
    ResourceNotFoundException,
)

logger = logging.getLogger(__name__)


class QuizGenerationTask:
    """Background task for quiz generation"""

    def __init__(self, redis_client: RedisClient):
        self._redis_client = redis_client

    async def generate_quiz_async(
            self,
            quiz_service: QuizService,
            prompt: str,
            quiz_id: UUID,
            user_id: str
    ):
        """
        Generate quiz asynchronously with progress tracking.
        
        Note: All validations (prompt, permissions, quiz existence) are performed
        SYNCHRONOUSLY in the API endpoint before this task starts. This task
        assumes validation has already passed and focuses on generation.

        Args:
            quiz_service: QuizService instance
            prompt: User's prompt for quiz generation
            quiz_id: UUID of the quiz
            user_id: ID of the user requesting generation

        Note:
            This method updates Redis progress throughout the generation process
        """
        quiz_id_str = str(quiz_id)

        try:
            # Set initial progress
            await self._redis_client.set_progress(
                quiz_id=quiz_id_str,
                status="PENDING",
                progress=0,
                message="Đang khởi tạo quá trình tạo câu hỏi...",
                total_questions=0
            )

            logger.info(f"Starting async quiz generation for quiz_id: {quiz_id}")

            # Update progress: Loading context
            await self._redis_client.set_progress(
                quiz_id=quiz_id_str,
                status="PROCESSING",
                progress=20,
                message="Đang tải nội dung khóa học...",
                total_questions=0
            )

            # Update progress: Generating questions
            await self._redis_client.set_progress(
                quiz_id=quiz_id_str,
                status="PROCESSING",
                progress=40,
                message="Đang phân tích nội dung và tạo câu hỏi...",
                total_questions=0
            )

            # Generate quiz questions
            # Note: Validation already done in API endpoint, this will skip re-validation
            questions_data = await quiz_service.generate_quiz(
                prompt=prompt,
                quiz_id=quiz_id,
                user_id=user_id
            )

            # Update progress: Saving to database
            await self._redis_client.set_progress(
                quiz_id=quiz_id_str,
                status="PROCESSING",
                progress=80,
                message="Đang lưu câu hỏi vào cơ sở dữ liệu...",
                total_questions=len(questions_data)
            )

            # Simulate slight delay for final processing
            await asyncio.sleep(0.5)

            # Update progress: Completed
            await self._redis_client.set_progress(
                quiz_id=quiz_id_str,
                status="COMPLETED",
                progress=100,
                message=f"Hoàn thành! Đã tạo {len(questions_data)} câu hỏi.",
                total_questions=len(questions_data)
            )

            logger.info(
                f"Successfully completed async quiz generation for quiz_id: {quiz_id}, "
                f"generated {len(questions_data)} questions"
            )

        except UnauthorizedException as e:
            logger.error(f"Unauthorized error in async quiz generation: {e}")
            await self._redis_client.set_progress(
                quiz_id=quiz_id_str,
                status="FAILED",
                progress=0,
                message="Lỗi xác thực: Token không hợp lệ hoặc đã hết hạn.",
                total_questions=0,
                error=str(e)
            )

        except AccessDeniedException as e:
            logger.error(f"Access denied in async quiz generation: {e}")
            await self._redis_client.set_progress(
                quiz_id=quiz_id_str,
                status="FAILED",
                progress=0,
                message="Lỗi phân quyền: Bạn không có quyền tạo câu hỏi cho bài quiz này.",
                total_questions=0,
                error=str(e)
            )

        except ResourceNotFoundException as e:
            logger.error(f"Resource not found in async quiz generation: {e}")
            await self._redis_client.set_progress(
                quiz_id=quiz_id_str,
                status="FAILED",
                progress=0,
                message="Lỗi: Không tìm thấy bài quiz hoặc khóa học.",
                total_questions=0,
                error=str(e)
            )

        except BadRequestException as e:
            logger.error(f"Bad request in async quiz generation: {e}")
            await self._redis_client.set_progress(
                quiz_id=quiz_id_str,
                status="FAILED",
                progress=0,
                message=f"Lỗi yêu cầu không hợp lệ: {str(e)}",
                total_questions=0,
                error=str(e)
            )

        except ValueError as e:
            logger.error(f"Value error in async quiz generation: {e}")
            await self._redis_client.set_progress(
                quiz_id=quiz_id_str,
                status="FAILED",
                progress=0,
                message=f"Lỗi xử lý dữ liệu: {str(e)}",
                total_questions=0,
                error=str(e)
            )

        except Exception as e:
            logger.exception(f"Unexpected error in async quiz generation: {e}")
            await self._redis_client.set_progress(
                quiz_id=quiz_id_str,
                status="FAILED",
                progress=0,
                message=f"Lỗi không mong đợi: {str(e)}",
                total_questions=0,
                error=str(e)
            )
