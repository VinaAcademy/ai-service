from typing import List

from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder


class PromptService:
    """
    Service quản lý prompts và templates
    """

    @staticmethod
    def build_quiz_creating_prompt(context: str, query: str, skills: str) -> str:
        """Build the prompt for MCQ generation"""
        return f"""Bạn là Giảng viên có học vị Tiến sĩ, chuyên gia tạo các bộ câu hỏi để kiểm tra kiến thức của sinh viên.

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

    KIẾN THỨC LIÊN QUAN: {skills}

    NỘI DUNG BÀI HỌC:
    {context}

    {self._format_instructions}

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
