"""
Chatbot Service - AI Agent with LangGraph and context-aware tools
Handles conversational AI with course discovery and lesson context retrieval
"""

import asyncio
import logging
from dataclasses import dataclass
from typing import Optional, List, AsyncGenerator

from langchain.agents import create_agent
from langchain_core.messages import SystemMessage
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.memory import MemorySaver

from src.config import get_settings
from src.factory.LLMFactory import LLMFactory
from src.services.agent_tools_service import AgentService
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
    user_id: Optional[str] = None
    user_name: Optional[str] = None
    user_email: Optional[str] = None
    user_roles: Optional[List[str]] = None
    lesson_id: Optional[str] = None
    course_id: Optional[str] = None
    custom_context: Optional[dict] = None


class ChatbotService:
    """
    Service for AI-powered chatbot using LangChain agents.
    
    Features:
    - Context-aware conversations (tracks user's current lesson/course)
    - Semantic course search via Eureka service discovery
    - Database-backed lesson content retrieval
    - Vietnamese-first educational assistant
    """

    def __init__(self, agent_tools_service: AgentService):
        self.agent_tools_service = agent_tools_service
        self.llm = LLMFactory.create(streaming=True)
        self.tools = agent_tools_service.create_langchain_tools()
        self.middlewares = agent_tools_service.create_langchain_middlewares()
        self.agent = self._create_agent()

    def _create_agent(self):
        """
        Create LangChain agent with tools.
        
        Returns:
            Configured agent executor
        """
        self.checkpointer = MemorySaver()
        agent = create_agent(
            model=self.llm,
            tools=self.tools,
            middleware=self.middlewares,
            checkpointer=self.checkpointer,
            system_prompt=PromptService.get_system_prompt(),
        )

        return agent

    async def stream_chat(
            self,
            user_message: str,
            context: ChatContext
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
                "messages": [
                    SystemMessage(content=PromptService.get_system_prompt()),
                    {"role": "user", "content": user_message}
                ],
            }
            config: RunnableConfig = {"configurable": {"thread_id": context.user_id}}

            logger.info(f"Streaming response for user {context.user_id}: {user_message[:50]}...")

            # Stream agent execution with state values
            async for token, metadata in self.agent.astream(agent_input,
                                                            config=config,
                                                            context=context,
                                                            stream_mode="messages"):
                if metadata:
                    if metadata['langgraph_node'] == 'tools':
                        yield {
                            "type": "tool_call",
                            "text": "Đang tìm kiếm...",
                        }
                    elif 'SummarizationMiddleware' in metadata['langgraph_node']:
                        yield {
                            "type": "summarization",
                            "text": "Đang tóm tắt cuộc trò chuyện...",
                        }
                if not token.content_blocks:
                    continue

                for block in token.content_blocks:
                    if metadata['langgraph_node'] == 'tools':
                        continue
                    if block['type'] != 'tool_call_chunk':
                        yield {
                            "type": block['type'],
                            "text": block['text'] if 'text' in block
                            else 'Đang suy nghĩ...',
                        }

                    if 'tool_call_chunks' not in token:
                        continue

                    for tool_chunk in token.tool_call_chunks:
                        if 'name' in tool_chunk and tool_chunk['name']:
                            yield {
                                "type": "tool_call",
                                "text": AgentService.get_agent_tool_text(tool_chunk['name'])
                            }


            logger.info(f"Completed streaming response for user {context.user_id}")

        except asyncio.CancelledError:
            logger.info(f"Chat stream cancelled for user {context.user_id}")
            raise

        except Exception as e:
            logger.error(f"❌ Error in stream chat: {str(e)}", exc_info=True)
            yield {
                "type": "error",
                "text": (
                    "Xin lỗi, đã có lỗi xảy ra khi xử lý yêu cầu của bạn. "
                    "Vui lòng thử lại sau."
                )
            }

    async def get_chat_history(self, user_id: str) -> List[dict]:
        """
        Retrieve chat history for a specific user.

        Args:
            user_id: The user's ID (used as thread_id)

        Returns:
            List of messages
        """
        try:
            config: RunnableConfig = {"configurable": {"thread_id": user_id}}
            state = self.agent.get_state(config)
            messages = state.values.get("messages", [])

            # Format messages
            formatted_messages = []
            for msg in messages:
                logger.debug(f"Message: {msg}")
                # Skip summarization messages
                if hasattr(msg, "metadata") and msg.metadata.get("langgraph_node") == "SummarizationMiddleware":
                    continue

                role = msg.type
                if role == 'human':
                    role = 'user'
                elif role == 'ai':
                    role = 'assistant'
                else:
                    continue  # Skip unknown roles
                if msg.content == "":
                    continue  # Skip empty messages

                formatted_messages.append({
                    "role": role,
                    "content": msg.content,
                    "id": getattr(msg, "id", None)
                })

            return formatted_messages
        except Exception as e:
            logger.error(f"❌ Error retrieving chat history: {str(e)}")
            return []

    async def clear_chat_history(self, user_id: str) -> bool:
        """
        Clear chat history for a specific user.

        Args:
            user_id: The user's ID (used as thread_id)

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # For MemorySaver, we can directly access storage to delete the thread
            if hasattr(self, 'checkpointer') and hasattr(self.checkpointer, 'storage'):
                if user_id in self.checkpointer.storage:
                    del self.checkpointer.storage[user_id]
                    logger.info(f"Cleared chat history for user {user_id}")
                else:
                    logger.info(f"No chat history found for user {user_id}")
                return True

            return False
        except Exception as e:
            logger.error(f"❌ Error clearing chat history: {str(e)}")
            return False
