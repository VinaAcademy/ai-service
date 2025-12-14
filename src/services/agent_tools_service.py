"""
Agent Tools Service - LangChain tools for AI agent chatbot
Provides context retrieval from database and semantic search via Eureka
"""

import logging
from typing import Optional
from uuid import UUID

from langchain.agents import AgentState
from langchain.agents.middleware import dynamic_prompt, ModelRequest, after_model
from langchain_core.tools import tool
from langgraph.prebuilt import ToolRuntime
from langgraph.runtime import Runtime

from src.config import get_settings
from src.db.session import AsyncSessionLocal
from src.repositories.lesson_repo import LessonRepository
from src.utils.service_utils import search_courses_semantic

logger = logging.getLogger(__name__)
settings = get_settings()


class AgentService:
    """
    Service for providing LangChain tools to the AI agent.
    Tools access database context and external services via Eureka.
    """

    def __init__(self):
        pass



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
            async with AsyncSessionLocal() as session:
                lesson_repository = LessonRepository(session)
                context = await lesson_repository.get_lesson_with_course_context(
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

    def create_langchain_middlewares(self):
        """
        Create middleware for LangChain tools to access service methods.

        Returns:
            Middleware function
        """

        service = self

        @dynamic_prompt
        def user_info_prompt(request: ModelRequest) -> str:
            context = request.runtime.context
            user_info = {
                "user_id": getattr(context, 'user_id', None),
                "user_name": getattr(context, 'user_name', None),
                "user_email": getattr(context, 'user_email', None),
                "user_roles": getattr(context, 'user_roles', []),
            }
            return f"User Info: {user_info}"

        @after_model
        def delete_old_messages(state: AgentState, runtime: Runtime) -> dict | None:
            """
            Middleware to delete old messages from runtime context
            to manage token limits.

            Args:
                state: Current agent state
                runtime: Current runtime
            Returns:
                Updated context or None
            """
            max_messages = 20
            messages = state.get("messages", [])
            if len(messages) > max_messages:
                # Keep only the latest max_messages
                state["messages"] = messages[-max_messages:]
                logger.info(
                    f"🗑️ Deleted old messages, kept last {max_messages} messages."
                )
            return None

        return [user_info_prompt, delete_old_messages]

    def create_langchain_tools(self):
        """
        Create LangChain tools for the AI agent.

        Returns:
            List of @tool decorated functions with ToolRuntime support
        """

        # Reference to self for use in tool closures
        service = self

        @tool
        async def search_courses(query: str,
                                 course_level: Optional[str] = None,
                                 min_price: Optional[float] = None,
                                 max_price: Optional[float] = None,
                                 min_rating: Optional[float] = None) -> str:
            """
            Search for relevant courses by topic or keyword using semantic AI search.

            Use this tool when the user asks about:
            - Course recommendations (e.g., "Tôi muốn học Python")
            - Finding courses by topic (e.g., "Khóa học về machine learning")
            - General course discovery

            IMPORTANT: Only provide optional parameters (course_level, min_price, max_price, min_rating)
            if the user EXPLICITLY mentions them in their request. Do not guess or infer these values.

            Args:
                query: User's search query in Vietnamese or English
                course_level: Optional filter for course level (e.g., "BEGINNER", "INTERMEDIATE", "ADVANCED"). Only use if user specifies level.
                min_price: Optional minimum price. Only use if user specifies price range.
                max_price: Optional maximum price. Only use if user specifies price range.
                min_rating: Optional minimum rating. Only use if user specifies rating.

            Returns:
                Formatted string with course recommendations
            """
            filters = {
                "courseLevel": course_level,
                "minPrice": min_price,
                "maxPrice": max_price,
                "minRating": min_rating
            }
            # Remove None values
            filters = {k: v for k, v in filters.items() if v is not None}

            result = await search_courses_semantic(query=query, filter=filters, size=5)

            if result["status"] != "SUCCESS" or not result.get("data"):
                return "❌ Không tìm thấy khóa học phù hợp. Vui lòng thử lại với từ khóa khác."

            courses = result["data"].get("content", [])
            if not courses:
                return "❌ Không có khóa học nào phù hợp với yêu cầu của bạn."

            # Format course list
            course_list = ["📚 **Các khóa học được đề xuất:**",
                           "Nếu bạn thấy khóa học đó không hợp lý thì bỏ ra khỏi danh sách gợi ý,",
                           "kết quả có thể không chính xác nên loại bỏ những khóa học không liên quan,",
                           "đường link gợi ý sẽ là https://vnacademy.io.vn/courses/{slug}",
                           "Dưới đây là danh sách các khóa học phù hợp với yêu cầu của bạn:\n"]
            for idx, course in enumerate(courses[:5], 1):
                image_url = course.get('image', '')
                if image_url and not image_url.startswith(('http://', 'https://')):
                    image_url = f"https://vnacademy.io.vn/api/images/view/{image_url}"

                course_list.append(
                    f"{idx}. **{course['name']}** ({course['level']})\n"
                    f"   - Hình ảnh: {image_url}\n"
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
                    f"� **Mô tả khóa học:** {lesson_context['course_description'][:500]}...",
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
