"""
Agent Tools Service - LangChain tools for AI agent chatbot
Provides context retrieval from database and semantic search via Eureka
"""

import logging
from typing import Optional
from uuid import UUID

import httpx
import py_eureka_client.eureka_client as eureka_client
from langchain_core.tools import tool
from langgraph.prebuilt import ToolRuntime

from src.config import get_settings
from src.repositories.lesson_repo import LessonRepository

logger = logging.getLogger(__name__)
settings = get_settings()


class AgentToolsService:
    """
    Service for providing LangChain tools to the AI agent.
    Tools access database context and external services via Eureka.
    """

    def __init__(self, lesson_repository: LessonRepository):
        self.lesson_repository = lesson_repository

    @staticmethod
    async def _get_vector_search_service_url() -> Optional[str]:
        """
        Resolve VECTOR-SEARCH-SERVICE from Eureka server.

        Returns:
            Base URL of the vector search service or None if not found
        """
        try:
            # Get service instance from Eureka
            service_url = await eureka_client.do_service_async(
                app_name="VECTOR-SEARCH-SERVICE",
                return_type="url"
            )
            if service_url:
                logger.info(f"✅ Resolved VECTOR-SEARCH-SERVICE: {service_url}")
                return service_url
            else:
                logger.warning("⚠️ VECTOR-SEARCH-SERVICE not found in Eureka")
                return None
        except Exception as e:
            logger.error(f"❌ Failed to resolve VECTOR-SEARCH-SERVICE: {str(e)}")
            return None

    @staticmethod
    async def search_courses_semantic(
            query: str, page: int = 0, size: int = 9
    ) -> dict:
        """
        Search courses using semantic search via VECTOR-SEARCH-SERVICE.

        Args:
            query: Search query (e.g., "Học python")
            page: Page number (default: 0)
            size: Page size (default: 9)

        Returns:
            API response with course list and pagination info
        """
        # base_url = await self._get_vector_search_service_url()
        base_url = 'https://api.vnacademy.io.vn'
        if not base_url:
            return {
                "status": "ERROR",
                "message": "Vector search service unavailable",
                "data": None
            }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    f"{base_url}/api/v1/courses/aisearch",
                    params={
                        "semantic": "true",
                        "keyword": query,
                        "page": page,
                        "size": size
                    }
                )
                response.raise_for_status()
                return response.json()
        except httpx.HTTPError as e:
            logger.error(f"❌ HTTP error during semantic search: {str(e)}")
            return {
                "status": "ERROR",
                "message": f"Search failed: {str(e)}",
                "data": None
            }
        except Exception as e:
            logger.error(f"❌ Unexpected error during semantic search: {str(e)}")
            return {
                "status": "ERROR",
                "message": f"Unexpected error: {str(e)}",
                "data": None
            }

    async def get_single_lesson_context(
            self, lesson_id: UUID
    ) -> Optional[dict]:
        """
        Get full course context for a specific lesson.

        Args:
            lesson_id: UUID of the lesson

        Returns:
            Dictionary with course, section, and lesson metadata or None
        """
        try:
            context = await self.lesson_repository.get_lesson_with_course_context(
                lesson_id=lesson_id
            )
            if context:
                logger.info(
                    f"✅ Retrieved lesson context for lesson {lesson_id}"
                )
            else:
                logger.warning(f"⚠️ No lesson found with ID {lesson_id}")
            return context
        except Exception as e:
            logger.error(
                f"❌ Failed to get lesson context for lesson {lesson_id}: {str(e)}"
            )
            return None

    def create_langchain_tools(self):
        """
        Create LangChain tools for the AI agent.

        Returns:
            List of @tool decorated functions with ToolRuntime support
        """

        # Reference to self for use in tool closures
        service = self

        @tool
        async def search_courses(query: str) -> str:
            """
            Search for relevant courses by topic or keyword using semantic AI search.

            Use this tool when the user asks about:
            - Course recommendations (e.g., "Tôi muốn học Python")
            - Finding courses by topic (e.g., "Khóa học về machine learning")
            - General course discovery

            Args:
                query: User's search query in Vietnamese or English

            Returns:
                Formatted string with course recommendations
                :param query:
            """
            result = await service.search_courses_semantic(query=query, size=5)

            if result["status"] != "SUCCESS" or not result.get("data"):
                return "❌ Không tìm thấy khóa học phù hợp. Vui lòng thử lại với từ khóa khác."

            courses = result["data"].get("content", [])
            if not courses:
                return "❌ Không có khóa học nào phù hợp với yêu cầu của bạn."

            # Format course list
            course_list = ["📚 **Các khóa học được đề xuất:**",
                           "Nếu bạn thấy khóa học đó không hợp lý thì bỏ ra khỏi danh sách gợi ý,",
                           "đường link gợi ý sẽ là https://vnacademy.io.vn/courses/{slug}",
                           "Dưới đây là danh sách các khóa học phù hợp với yêu cầu của bạn:\n"]
            for idx, course in enumerate(courses[:5], 1):
                course_list.append(
                    f"{idx}. **{course['name']}** ({course['level']})\n"
                    f"   - Danh mục: {course.get('categoryName', 'N/A')}\n"
                    f"   - Giảng viên: {course.get('instructorName', 'N/A')}\n"
                    f"   - Mô tả: {course['description'][:500]}...\n"
                    f"   - Ngôn ngữ: {course['language']}\n"
                    f"   - Giá: {course['price']:,} VNĐ\n"
                    f"   - Đánh giá: {course['rating']}/5 ({course['totalRating']} đánh giá)\n"
                    f"   - Học viên: {course['totalStudent']} người\n"
                    f"   - Slug: {course.get('slug', 'N/A')}\n"
                )

            return "\n".join(course_list)

        @tool
        async def get_lesson_context(lesson_id: str, runtime: ToolRuntime) -> str:
            """
            Get lesson content and course context when the user is studying a specific lesson.

            Use this tool when:
            - User asks questions related to their current lesson
            - User needs explanation about lesson content
            - Context shows user is in a lesson (lesson_id exists in runtime.context)

            Args:
                lesson_id: UUID of the lesson (provided in ChatContext)

            Returns:
                Formatted string with lesson and course context
                :param lesson_id:
                :param runtime:
            """
            # Check if lesson_id is in context
            context = runtime.context
            if not hasattr(context, 'lesson_id') or not context.lesson_id:
                return "ℹ️ Không có bài học cụ thể đang được học. Vui lòng chọn một bài học để bắt đầu."

            try:
                # Parse lesson_id as UUID
                lesson_uuid = UUID(lesson_id)

                # Get lesson context
                lesson_context = await service.get_single_lesson_context(
                    lesson_id=lesson_uuid
                )

                if not lesson_context:
                    return "❌ Không tìm thấy nội dung bài học."

                # Format context
                context_text = [
                    f"📖 **Khóa học:** {lesson_context['course_name']}",
                    f"� **Mô tả khóa học:** {lesson_context['course_description'][:200]}...",
                    f"🌐 **Ngôn ngữ:** {lesson_context['course_language']}",
                    f"🎯 **Cấp độ:** {lesson_context['course_level']}",
                    f"🗂️ **Phần:** {lesson_context['section_title']}\n",
                    f"📚 **Bài học hiện tại:** {lesson_context['lesson_title']}",
                    f"📖 **Loại bài học:** {lesson_context['lesson_type'] or 'Chưa xác định'}",
                ]

                if lesson_context.get('lesson_description'):
                    context_text.append(
                        f"📄 **Mô tả bài học:** {lesson_context['lesson_description']}"
                    )

                return "\n".join(context_text)

            except ValueError:
                return "❌ ID bài học không hợp lệ."
            except Exception as e:
                logger.error(f"Error getting lesson context: {str(e)}")
                return f"❌ Lỗi khi lấy thông tin bài học: {str(e)}"

        return [search_courses, get_lesson_context]
