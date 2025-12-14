import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware

from src.api.v1.router import api_router
from src.clients.eureka_client import register_with_eureka, deregister_from_eureka
from src.config import get_settings
from src.db.session import init_db, close_db
from src.dependencies.services import get_redis_client
from src.utils.exception_handlers import register_exception_handlers
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

    # Initialize Redis connection
    try:
        redis_client = await get_redis_client()
        logger.info("Redis client initialized")
        if not await redis_client.ping():
            logger.warning("Redis client ping failed")
    except Exception as e:
        logger.warning(f"Failed to initialize Redis client: {e}")

    yield

    # SHUTDOWN
    logger.info(f"🛑 Shutting down {settings.app_name}")
    await deregister_from_eureka()
    await close_db()

    # Close Redis connection
    try:
        redis_client = await get_redis_client()
        await redis_client.disconnect()
        logger.info("Redis client disconnected")
    except Exception as e:
        logger.warning(f"Failed to disconnect Redis client: {e}")


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

# Register global exception handlers
register_exception_handlers(app)


# Health check
@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "service": settings.app_name,
        "version": settings.app_version,
        "environment": settings.environment,
    }


@app.get("/")
async def root():
    return {
        "message": f"Welcome to {settings.app_name}",
        "version": settings.app_version,
        "docs": "/docs",
    }


# Include routers
app.include_router(api_router, prefix="/api/v1")