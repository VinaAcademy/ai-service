from fastapi import APIRouter

from src.api.v1.endpoints import quiz_controller, chatbot_controller

api_router = APIRouter()

# Include quiz endpoints
api_router.include_router(quiz_controller.router)

# Include chatbot endpoints
api_router.include_router(chatbot_controller.router)
