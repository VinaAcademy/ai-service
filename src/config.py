from functools import lru_cache
from typing import Optional

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # App
    app_name: str = "chatbot-service"
    app_version: str = "1.0.0"
    app_host: str = "127.0.0.1"
    app_port: int = 8000
    environment: str = "development"

    # Eureka
    eureka_server_url: str = "http://localhost:8761/eureka/"
    instance_host: str = "localhost"
    instance_port: int = 8000

    # Database
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/vinaacademy_chatbot"
    sync_database_url: str = "postgresql://postgres:postgres@localhost:5432/vinaacademy_chatbot"

    # LangChain / AI
    openai_api_key: str | None = ""
    google_api_key: str = ""
    hugging_api_key: str = ""
    llm_provider: str = "google"
    openai_model_name: str = "gpt-3.5-turbo"
    gemini_model_name: str = "gemini-2.0-flash"
    temperature: float = 0.7
    max_tokens: int = 500
    embedding_model: str = "text-embedding-3-small"

    # RAG settings
    vector_dimension: int = 1536  # OpenAI embedding dimension
    retrieval_top_k: int = 5  # Number of documents to retrieve
    similarity_threshold: float = 0.7  # Minimum similarity score

    # Retriever Hyperparameters
    top_k: int = 10
    rrf_k: int = 60
    candidates_n: int = 20

    # Redis
    redis_url: Optional[str] = None

    # Kafka
    kafka_bootstrap_servers: Optional[str] = None
    kafka_topic: str = "chatbot-events"

    # Logging
    log_level: str = "DEBUG"

    class Config:
        env_file = ".env"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    return Settings()
