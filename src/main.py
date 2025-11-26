import logging
import os
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware
from starlette.responses import StreamingResponse

from src.clients.eureka_client import register_with_eureka, deregister_from_eureka
from src.config import get_settings
from src.db.session import init_db, close_db
from src.utils.log import setup_logging

setup_logging()
logger = logging.getLogger(__name__)
settings = get_settings()


@asynccontextmanager
async def lifespan(fastapi_app: FastAPI) -> AsyncGenerator:
    """Lifecycle events"""
    # STARTUP
    logger.info(f"🚀 Starting {settings.app_name} v{settings.app_version}")
    await init_db()
    await register_with_eureka()

    yield

    # SHUTDOWN
    logger.info(f"🛑 Shutting down {settings.app_name}")
    await deregister_from_eureka()
    await close_db()


# Create app
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Chatbot Service with LangChain",
    lifespan=lifespan,
    docs_url="/docs" if settings.environment == "development" else None,
    redoc_url="/redoc" if settings.environment == "development" else None,
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # TODO: Configure for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Health check
@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "service": settings.app_name,
        "version": settings.app_version,
        "environment": settings.environment
    }


@app.get("/")
async def root():
    return {
        "message": f"Welcome to {settings.app_name}",
        "version": settings.app_version,
        "docs": "/docs"
    }


# Include routers
from src.api.v1.router import api_router
app.include_router(api_router, prefix="/api/v1")
# TODO: Include routers sau khi tạo
# from src.api.v1.router import api_router
# app.include_router(api_router, prefix="/api/v1")

from langchain_google_genai import ChatGoogleGenerativeAI

# Khởi tạo mô hình
llm = ChatGoogleGenerativeAI(
    model=settings.openai_model_name,
    temperature=0.7,
    max_tokens=None,
    timeout=None,
    max_retries=2,
    streaming=True,
    google_api_key=settings.google_api_key
)

from langchain_core.messages import HumanMessage, SystemMessage


def event_stream(prompt: str):
    messages = [
        SystemMessage(content="You are a helpful assistant that instructs newbie to cooking."),
        HumanMessage(content=prompt)
    ]
    for chunk in llm.stream(messages):
        yield f"data: {chunk.content}\n\n"

prompt = """Cách làm bánh mì Việt Nam như thế nào?"""


@app.get("/stream")
def stream_response():
    return StreamingResponse(event_stream(prompt), media_type="text/event-stream")

