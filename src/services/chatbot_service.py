"""
Chatbot Service - AI Agent with LangGraph and context-aware tools
Handles conversational AI with course discovery and lesson context retrieval
"""

import logging
from dataclasses import dataclass
from typing import Optional, List, AsyncGenerator

from langchain.agents import create_agent
from langchain_core.messages import SystemMessage
from langgraph.checkpoint.postgres import PostgresSaver

from src.config import get_settings
from src.factory.LLMFactory import LLMFactory
from src.services.agent_tools_service import AgentToolsService
from src.services.prompt_service import PromptService

logger = logging.getLogger(__name__)
settings = get_settings()


@dataclass
class ChatContext:
    """
    Context tracking for chatbot conversations.
    
    Attributes:
        user_id: UUID of the current user
        lesson_id: Optional UUID of the lesson user is currently viewing
        course_id: Optional UUID of the course user is browsing
    """
    user_id: str
    lesson_id: Optional[str] = None
    course_id: Optional[str] = None


class ChatbotService:
    """
    Service for AI-powered chatbot using LangChain agents.
    
    Features:
    - Context-aware conversations (tracks user's current lesson/course)
    - Semantic course search via Eureka service discovery
    - Database-backed lesson content retrieval
    - Vietnamese-first educational assistant
    """

    def __init__(self, agent_tools_service: AgentToolsService):
        self.agent_tools_service = agent_tools_service
        self.llm = LLMFactory.create(streaming=True)
        self.tools = agent_tools_service.create_langchain_tools()
        self.agent = self._create_agent()

    def _create_agent(self):
        """
        Create LangChain agent with tools.
        
        Returns:
            Configured agent executor
        """
        with PostgresSaver.from_conn_string(settings.sync_database_url) as checkpointer:
            checkpointer.setup()
            agent = create_agent(
                model=self.llm,
                tools=self.tools,
                # checkpointer=checkpointer,
                system_prompt=SystemMessage(content=PromptService.get_system_prompt()),
            )

        return agent

    async def stream_chat(
            self,
            user_message: str,
            context: ChatContext,
            conversation_history: Optional[List[dict]] = None
    ) -> AsyncGenerator[dict, None]:
        """
        Process a user message and stream the AI's response, including tool activities.

        This method orchestrates the conversation using the configured LangChain agent.
        It maintains conversation state via the checkpointer and streams back
        intermediate steps (like tool usage) and the final generated response.

        Args:
            user_message (str): The input message from the user.
            context (ChatContext): The context of the conversation, including user identity
                                   and current navigation state (lesson/course).
            conversation_history (Optional[List[dict]]): A list of previous messages to provide
                                                       context for the LLM. Defaults to None.

        Yields:
            dict: Streaming events representing the agent's thought process and output.
                  Structure: {"type": str, "text": str}
                  
                  Event types may include:
                  - "tool_call": When the agent is executing a tool (e.g., searching).
                  - "text": Content blocks of the AI's textual response.
                  - "error": If an exception occurs during processing.
        """
        try:
            # Prepare agent input
            agent_input = {
                "messages": [{
                    "role": "user",
                    "content": user_message
                }],
                # "user_id": context.user_id,
                # "lesson_id": context.lesson_id,
                # "course_id": context.course_id,
            }
            # config = {"configurable": {"thread_id": context.user_id if context.user_id else None}}

            logger.info(f"Streaming response for user {context.user_id}: {user_message[:50]}...")

            # Stream agent execution with state values
            async for token, metadata in self.agent.astream(agent_input, stream_mode="messages"):
                if metadata and metadata['langgraph_node'] == 'tools':
                    yield {
                        "type": "tool_call",
                        "text": "Đang tìm kiếm...",
                    }
                if token.content_blocks:
                    for block in token.content_blocks:
                        if metadata['langgraph_node'] == 'tools':
                            continue
                        yield {
                            "type": block['type'],
                            "text": block['text'] if 'text' in block
                            else 'Đang suy nghĩ...',
                        }
            logger.info(f"Completed streaming response for user {context.user_id}")


        except Exception as e:
            logger.error(f"❌ Error in stream chat: {str(e)}", exc_info=True)
            yield {
                "type": "error",
                "text": (
                    "Xin lỗi, đã có lỗi xảy ra khi xử lý yêu cầu của bạn. "
                    "Vui lòng thử lại sau."
                )
            }
