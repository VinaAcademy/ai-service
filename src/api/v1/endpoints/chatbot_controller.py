"""
Chatbot Controller - REST API endpoints for AI chatbot
Handles chat interactions with context-aware AI agent
"""

import asyncio
import json
import logging
from typing import Optional, List

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from starlette.responses import StreamingResponse

from src.dependencies.services import get_chatbot_service
from src.schemas.generic import ApiResponse
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
    custom_context: Optional[dict] = Field(None, description="Custom context")


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
        course_id=request.course_id,
        custom_context=request.custom_context or {}
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
        except asyncio.CancelledError:
            logger.info(f"User {user_info.get('email')} stopped the chat stream.")
            raise
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


@router.get(
    "/history",
    summary="Get Chat History",
    description="Retrieve chat history for the current user.",
    response_model=ApiResponse[List[ChatMessage]]
)
async def get_chat_history(
        chatbot_service: ChatbotService = Depends(get_chatbot_service),
        user_info: dict = Depends(AuthService.get_user_info)
) -> ApiResponse[List[ChatMessage]]:
    """
    Get chat history for the authenticated user.
    """
    user_id = user_info.get("user_id")
    if not user_id:
        raise ValueError("User ID is required to fetch chat history.")

    history = await chatbot_service.get_chat_history(user_id)
    return ApiResponse.success(data=history)


@router.delete(
    "/history",
    summary="Clear Chat History",
    description="Clear chat history for the current user.",
    response_model=ApiResponse[bool]
)
async def clear_chat_history(
        chatbot_service: ChatbotService = Depends(get_chatbot_service),
        user_info: dict = Depends(AuthService.get_user_info)
) -> ApiResponse[bool]:
    """
    Clear chat history for the authenticated user.
    """
    user_id = user_info.get("user_id")
    if not user_id:
        raise ValueError("User ID is required to clear chat history.")

    result = await chatbot_service.clear_chat_history(user_id)
    if result:
        return ApiResponse.success(data=True, message="Đã xóa lịch sử chat thành công.")
    else:
        return ApiResponse.error(message="Không thể xóa lịch sử chat.", status_code=500)
