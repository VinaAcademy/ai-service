"""
Chatbot Controller - REST API endpoints for AI chatbot
Handles chat interactions with context-aware AI agent
"""

import json
import logging
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from starlette.responses import StreamingResponse

from src.dependencies.services import get_chatbot_service
from src.services.auth_service import AuthService
from src.services.chatbot_service import ChatbotService, ChatContext

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chatbot", tags=["Chatbot"])


# =============================
#   Request/Response Schemas
# =============================
class ChatMessage(BaseModel):
    """Single chat message"""
    role: str = Field(..., description="Message role: 'user' or 'assistant'")
    content: str = Field(..., description="Message content")


class ChatRequest(BaseModel):
    """Request body for chat endpoint"""
    message: str = Field(..., min_length=1, max_length=2000, description="User's message")
    lesson_id: Optional[str] = Field(None, description="Current lesson ID if user is in a lesson")
    course_id: Optional[str] = Field(None, description="Current course ID if user is browsing")


class ChatResponse(BaseModel):
    """Response from chatbot"""
    message: str = Field(..., description="AI assistant's response")
    context: dict = Field(..., description="Conversation context")


@router.post(
    "/chat/stream",
    summary="Chat with Streaming Response",
    description="Stream AI responses with tool calls and final response for real-time UI updates."
)
async def chat_stream(
        request: ChatRequest,
        chatbot_service: ChatbotService = Depends(get_chatbot_service),
        user_info: dict = Depends(AuthService.get_user_info)
) -> StreamingResponse:
    """
    Stream chat responses in real-time (Server-Sent Events).

    Same functionality as `/chat` but streams the response with:
    - Tool calls (when agent searches courses or fetches lesson context)
    - Final response (AI's answer to user)

    **Response Format:** `text/event-stream`

    **Event Types:**
    ```json
    {"type": "tool_call", "text": "Đang tìm kiếm..."}
    {"type": "text", "text": "Tôi"}
    {"type": "error", "text": "Error description"}
    ```
    """
    logger.info(
        f"Received streaming chat request from user {user_info['email']}: {request.message[:50]}..."
    )

    # Create chat context
    context = ChatContext(
        user_id=user_info.get("user_id", None),
        user_name=user_info.get("full_name", "Người dùng"),
        user_email=user_info.get("email", ""),
        user_roles=user_info.get("user_roles", []),
        lesson_id=request.lesson_id,
        course_id=request.course_id
    )

    async def event_stream():
        """Generate SSE stream with structured events"""
        try:
            async for event in chatbot_service.stream_chat(
                    user_message=request.message,
                    context=context
            ):
                # Send event as JSON
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
        except Exception as e:
            logger.error(f"Error in streaming chat: {str(e)}")
            error_event = {
                "type": "error",
                "text": f"Lỗi: {str(e)}"
            }
            yield f"data: {json.dumps(error_event, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream"
    )


@router.get(
    "/health",
    summary="Chatbot Health Check",
    description="Check if chatbot service is ready"
)
async def health_check(
        chatbot_service: ChatbotService = Depends(get_chatbot_service)
) -> dict:
    """
    Health check endpoint for chatbot service.

    Returns:
        Service status and configuration
    """
    return {
        "status": "healthy",
        "service": "chatbot",
        "llm_provider": chatbot_service.llm.__class__.__name__,
        "tools_count": len(chatbot_service.tools)
    }
