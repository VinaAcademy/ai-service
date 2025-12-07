from typing import List

from src.model import Lesson


class PromptService:
    """
    Service quản lý prompts và templates
    """

    @staticmethod
    def build_quiz_creating_prompt(context: str, query: str, instructions: str) -> str:
        """Build the prompt for MCQ generation"""
        return f"""Bạn là Giảng viên có học vị Tiến sĩ, chuyên gia tạo các bộ câu hỏi để kiểm tra kiến thức của sinh viên.

    YÊU CẦU BẮT BUỘC:
    - TẤT CẢ nội dung sinh ra (câu hỏi, đáp án, giải thích, JSON) phải **100% bằng tiếng Việt**.
    - Tuyệt đối **không dùng tiếng Anh** trong bất kỳ phần nào trừ khi văn bản gốc trong context có chứa tiếng Anh.


    YÊU CẦU TẠO CÂU HỎI:
    {query}

    QUY TẮC BẮT BUỘC:
    1. Số lượng câu hỏi tạo ra phải đảm bảo bằng đúng số lượng câu hỏi mà tôi yêu cầu
    2. Hãy tự chọn loại câu hỏi phù hợp nhất cho từng câu:
       - SINGLE_CHOICE: Câu hỏi trắc nghiệm một đáp án đúng (4 lựa chọn, chỉ 1 đáp án đúng)
       - MULTIPLE_CHOICE: Câu hỏi trắc nghiệm nhiều đáp án đúng (4 lựa chọn, có thể có nhiều đáp án đúng)
       - TRUE_FALSE: Câu hỏi Đúng/Sai (chỉ có 2 lựa chọn: "Đúng" và "Sai")
    3. Mỗi câu hỏi PHẢI CÓ phần giải thích (explanation) cho đáp án đúng
    4. Điểm mặc định cho mỗi câu hỏi là 1.0
    5. QUAN TRỌNG: Mỗi câu hỏi PHẢI CÓ trường "answers" là một mảng các đáp án

    NỘI DUNG BÀI HỌC:
    {context}

    {instructions}

    VÍ DỤ OUTPUT ĐÚNG ĐỊNH DẠNG:
    ```json
    {{
      "data": [
        {{
          "question_text": "Câu hỏi mẫu?",
          "explanation": "Giải thích đáp án đúng",
          "point": 1.0,
          "question_type": "SINGLE_CHOICE",
          "answers": [
            {{"answer_text": "Đáp án A", "is_correct": true}},
            {{"answer_text": "Đáp án B", "is_correct": false}},
            {{"answer_text": "Đáp án C", "is_correct": false}},
            {{"answer_text": "Đáp án D", "is_correct": false}}
          ]
        }}
      ]
    }}
    ```

    CHỈ TRẢ VỀ JSON, KHÔNG CÓ TEXT KHÁC."""

    @staticmethod
    def build_course_context(lessons_context: List[dict], quiz: Lesson) -> str:
        """
        Build a context string from course/section/lesson information.

        Args:
            lessons_context: List of dicts with course, section, and lesson info
            quiz: The quiz Lesson object

        Returns:
            Formatted context string for LLM
        """
        if not lessons_context:
            return f"Quiz: {quiz.title}"

        # Extract course info from first item (same for all)
        first = lessons_context[0]

        context_parts = [
            "=== THÔNG TIN KHÓA HỌC ===",
            f"Tên khóa học: {first.get('course_name', 'N/A')}",
            f"Mô tả khóa học: {first.get('course_description', 'N/A')}",
            f"Ngôn ngữ: {first.get('course_language', 'tiếng Việt')}",
            f"Cấp độ: {first.get('course_level', 'N/A')}",
            "",
            "=== THÔNG TIN SECTION ===",
            f"Tên section: {first.get('section_title', 'N/A')}",
            "",
            "=== DANH SÁCH BÀI HỌC TRONG SECTION ===",
        ]

        for lesson in lessons_context:
            if lesson.get('lesson_id'):
                lesson_info = (
                    f"- {lesson.get('lesson_title', 'N/A')} "
                    f"(Loại: {lesson.get('lesson_type', 'N/A')})"
                )
                if lesson.get('lesson_description'):
                    lesson_info += f"\n  Mô tả: {lesson.get('lesson_description')}"
                context_parts.append(lesson_info)

        context_parts.extend([
            "",
            "=== QUIZ HIỆN TẠI ===",
            f"Tên quiz: {quiz.title}",
            f"Mô tả quiz: {quiz.description or 'N/A'}",
            "",
        ])

        return "\n".join(context_parts)
