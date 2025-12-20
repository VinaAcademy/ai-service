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
from src.repositories.course_repo import CourseRepository
from src.repositories.lesson_repo import LessonRepository
from src.services.prompt_service import PromptService
from src.utils.service_utils import search_courses_semantic, search_courses_keyword

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

    async def get_course_context(self, course_id: UUID) -> Optional[dict]:
        """
        Get full context for a specific course.

        Args:
            course_id: UUID of the course

        Returns:
            Dictionary with course details or None
        """
        try:
            async with AsyncSessionLocal() as session:
                course_repository = CourseRepository(session)
                context = await course_repository.get_course_details(course_id)
                if context:
                    logger.info(f"✅ Retrieved course context for course {course_id}")
                else:
                    logger.warning(f"⚠️ No course found with ID {course_id}")
                return context
        except Exception as e:
            logger.error(f"❌ Failed to get course context for course {course_id}: {str(e)}")
            return None

    def create_langchain_middlewares(self):
        """
        Create middleware for LangChain tools to access service methods.

        Returns:
            Middleware function
        """
        @dynamic_prompt
        def context_info(request: ModelRequest) -> str:
            context = request.runtime.context
            user_info = {
                "user_id": getattr(context, 'user_id', None),
                "user_name": getattr(context, 'user_name', None),
                "user_email": getattr(context, 'user_email', None),
                "user_roles": getattr(context, 'user_roles', []),
                "lesson_id": getattr(context, 'lesson_id', None),
                "course_id": getattr(context, 'course_id', None),
                "custom_context": getattr(context, 'custom_context', {}),
            }
            return f"Context Info: {user_info}"

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

        return [context_info, delete_old_messages]

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
            Tìm kiếm và gợi ý khóa học theo chủ đề/ngữ cảnh người dùng.

            Khi nào dùng:
            - Người dùng hỏi: “Muốn học X”, “Khóa học về Y”, “Gợi ý khóa học Z”.
            - Không dùng để lấy nội dung bài học cụ thể (dùng get_lesson_context) hoặc chi tiết khóa học (dùng get_course_context).

            Quy tắc dùng bộ lọc (KHÔNG SUY DIỄN):
            - Chỉ truyền `course_level`, `min_price`, `max_price`, `min_rating` khi người dùng NÓI RÕ trong câu hỏi.
            - Không tự đoán cấp độ, giá tiền hay đánh giá. Nếu không thấy trong yêu cầu, bỏ qua các tham số này.

            Tham số:
            - query: Câu hỏi/từ khóa của người dùng (Việt/Anh).
            - course_level: "BEGINNER" | "INTERMEDIATE" | "ADVANCED" (chỉ khi người dùng yêu cầu).
            - min_price / max_price: Khoảng giá (chỉ khi người dùng yêu cầu).
            - min_rating: Điểm đánh giá tối thiểu (chỉ khi người dùng yêu cầu).

            Ví dụ:
            - “Gợi ý khóa học Python cho người mới bắt đầu, giá dưới 500k” → set course_level="BEGINNER", max_price=500000
            - “Khóa học Machine Learning chất lượng” → chỉ truyền query, semantically=True
            - “Tìm các khóa Java rating từ 4.5 trở lên” → set min_rating=4.5

            Kết quả:
            - Trả về chuỗi văn bản đã format (tên, cấp độ, danh mục, giảng viên, giá, đánh giá...).
            - Nếu không tìm thấy: trả về thông báo lỗi thân thiện bằng tiếng Việt.
            """
            filters = {
                "courseLevel": course_level,
                "minPrice": min_price,
                "maxPrice": max_price,
                "minRating": min_rating
            }
            # Remove None values
            filters = {k: v for k, v in filters.items() if v is not None}

            result = await search_courses_keyword(keyword=query, size=5, filters=filters)
            if result['status'] == 'SUCCESS' and result.get('data') and result['data'].get('content', []):
                courses = result['data'].get('content')
                return PromptService.get_courses_recommend_prompt(courses)

            result = await search_courses_semantic(query=query, filters=filters, size=5)

            if result["status"] != "SUCCESS" or not result.get("data"):
                return "❌ Không tìm thấy khóa học phù hợp. Vui lòng thử lại với từ khóa khác."

            courses = result["data"].get("content", [])
            if not courses:
                return "❌ Không có khóa học nào phù hợp với yêu cầu của bạn."

            return PromptService.get_courses_recommend_prompt(courses)

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

                if lesson_context.get('lesson_type') == 'READING' and lesson_context.get('reading_content'):
                    context_text.append(
                        f"\n📝 **Nội dung bài đọc:**\n{lesson_context['reading_content']}"
                    )

                return "\n".join(context_text)

            except ValueError:
                return "❌ ID bài học không hợp lệ."
            except Exception as e:
                logger.error(f"Error getting lesson context: {str(e)}")
                return f"❌ Lỗi khi lấy thông tin bài học: {str(e)}"

        @tool
        async def get_course_context(course_id: str, runtime: ToolRuntime) -> str:
            """
            Get course content and context when the user is viewing a specific course.

            Use this tool when:
            - User asks questions related to the course they are viewing
            - User needs explanation about course structure or content
            - Context shows user is in a course (course_id exists in runtime.context)

            Args:
                course_id: UUID of the course (provided in ChatContext)

            Returns:
                Formatted string with course context
            """
            # Check if course_id is in context
            context = runtime.context
            if not hasattr(context, 'course_id') or not context.course_id:
                return "ℹ️ Không có khóa học cụ thể đang được xem. Vui lòng chọn một khóa học."

            try:
                # Parse course_id as UUID
                course_uuid = UUID(course_id)

                # Get course context
                course_context = await service.get_course_context(course_id=course_uuid)

                if not course_context:
                    return "❌ Không tìm thấy thông tin khóa học."

                # Format context
                context_text = [
                    f"📖 **Khóa học:** {course_context['course_name']}",
                    f"ℹ️ **Mô tả:** {course_context['course_description'][:500]}...",
                    f"🌐 **Ngôn ngữ:** {course_context['course_language']}",
                    f"🎯 **Cấp độ:** {course_context['course_level']}",
                    f"💰 **Giá:** {course_context['price']:,} VNĐ",
                    f"⭐ **Đánh giá:** {course_context['rating']}/5",
                    f"👥 **Học viên:** {course_context['total_student']}",
                    "\n**Danh sách các phần học:**"
                ]

                for section in course_context['sections']:
                    context_text.append(f"\n📂 **{section['title']}**")
                    for lesson in section['lessons']:
                        context_text.append(f"  - {lesson['title']} ({lesson['type']})")

                return "\n".join(context_text)

            except ValueError:
                return "❌ ID khóa học không hợp lệ."
            except Exception as e:
                logger.error(f"Error getting course context: {str(e)}")
                return f"❌ Lỗi khi lấy thông tin khóa học: {str(e)}"

        return [search_courses, get_lesson_context, get_course_context]

    @staticmethod
    def get_agent_tool_text(tool_name: str) -> str:
        """
        Get the names of the tools provided by the agent.

        Returns:
            List of tool names
        """
        name_to_text = {
            "search_courses": "Đang tìm kiếm khóa học...",
            "get_lesson_context": "Đang lấy thông tin bài học...",
            "get_course_context": "Đang lấy thông tin khóa học..."
        }

        return name_to_text.get(tool_name, "Đang xử lý...")
