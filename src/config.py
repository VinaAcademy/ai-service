from typing import Optional

from pydantic_settings import BaseSettings

from functools import lru_cache


class Settings(BaseSettings):
    # App
    app_name: str = "chatbot-service"
    app_version: str = "1.0.0"
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    environment: str = "development"

    # Eureka
    eureka_server_url: str = "http://localhost:8761/eureka/"
    instance_host: str = "localhost"
    instance_port: int = 8000

    # Database
    database_url: str = "sqlite+aiosqlite:///./test.db"
    sync_database_url: str = "sqlite:///./test.db"

    # LangChain / AI
    openai_api_key: str = ""
    google_api_key: str = ""
    model_name: str = "gpt-3.5-turbo"
    gemini_model_name: str = "gemini-2.0-flash"
    temperature: float = 0.7
    max_tokens: int = 500

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
    log_level: str = "INFO"

    class Config:
        env_file = ".env"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    return Settings()
