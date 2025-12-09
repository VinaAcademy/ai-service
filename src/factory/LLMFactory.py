from typing import Optional


class LLMFactory:
    @staticmethod
    def create(
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
            streaming: bool = False,
    ):
        """
        Create an LLM instance based on the configured provider.

        Args:
            max_tokens: Override default max_tokens (useful for longer outputs like quiz generation)
            temperature: Override default temperature
            streaming: Whether to enable streaming (default False for structured output)

        Returns:
            LLM instance (ChatGoogleGenerativeAI or ChatOpenAI)
        """
        from src.config import get_settings

        settings = get_settings()

        # Use provided values or fall back to settings
        _max_tokens = max_tokens or settings.max_tokens
        _temperature = temperature if temperature is not None else settings.temperature

        if settings.llm_provider == "google":
            from langchain_google_genai import ChatGoogleGenerativeAI

            return ChatGoogleGenerativeAI(
                model=settings.gemini_model_name,
                temperature=_temperature,
                max_tokens=_max_tokens,
                timeout=None,
                max_retries=2,
                streaming=streaming,
                google_api_key=settings.google_api_key,
            )

        if settings.llm_provider == "openai":
            from langchain_openai import ChatOpenAI

            return ChatOpenAI(
                model=settings.openai_model_name,
                temperature=_temperature,
                max_tokens=_max_tokens,
                api_key=settings.openai_api_key,
                streaming=streaming,
            )

        raise ValueError(f"Unsupported LLM provider: {settings.llm_provider}")
