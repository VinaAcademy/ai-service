import json
import logging
import re
from typing import TypeVar, Type

from langchain_core.output_parsers import PydanticOutputParser
from pydantic import ValidationError, BaseModel

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


class ParserUtils:
    @staticmethod
    def parse_with_fallback(content: str, parser: PydanticOutputParser, model_cls: Type[T]) -> T:
        # Check for truncated response
        if ParserUtils._is_truncated(content):
            logger.error("LLM response appears to be truncated (incomplete JSON)")
            raise ValueError(
                "LLM response was truncated. Try requesting fewer questions or increase max_tokens."
            )

        # Strategy 1: Direct parsing
        try:
            return parser.parse(content)
        except (ValidationError, Exception) as e:
            logger.warning(f"Direct parsing failed: {e}")

        # Strategy 2: Extract JSON from markdown code block
        try:
            json_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", content)
            if json_match:
                json_str = json_match.group(1)
                return parser.parse(json_str)
        except (ValidationError, Exception) as e:
            logger.warning(f"Markdown extraction failed: {e}")

        # Strategy 3: Find JSON object directly
        try:
            json_match = re.search(r"\{[\s\S]*}", content)
            if json_match:
                json_str = json_match.group(0)
                data = json.loads(json_str)
                return model_cls.model_validate(data)
        except (ValidationError, json.JSONDecodeError, Exception) as e:
            logger.warning(f"JSON extraction failed: {e}")

        # Strategy 4: Try to fix common issues and parse
        try:
            # Remove any leading/trailing non-JSON content
            cleaned = content.strip()
            if cleaned.startswith("```"):
                cleaned = re.sub(r"^```\w*\n?", "", cleaned)
                cleaned = re.sub(r"\n?```$", "", cleaned)

            data = json.loads(cleaned)
            return model_cls.model_validate(data)
        except (ValidationError, json.JSONDecodeError, Exception) as e:
            logger.error(f"All parsing strategies failed. Last error: {e}")
            logger.debug(f"Raw content was: {content[:500]}...")
            raise ValueError(f"Failed to parse LLM output: {e}")

    @staticmethod
    def _is_truncated(content: str) -> bool:
        """
        Check if the LLM response appears to be truncated.

        Args:
            content: Raw LLM output string

        Returns:
            True if response appears truncated
        """
        content = content.strip()

        # Check if JSON is properly closed
        open_braces = content.count("{")
        close_braces = content.count("}")
        open_brackets = content.count("[")
        close_brackets = content.count("]")

        if open_braces != close_braces or open_brackets != close_brackets:
            logger.warning(
                f"Unbalanced JSON: {{ {open_braces}/{close_braces} }}, [ {open_brackets}/{close_brackets} ]"
            )
            return True

        # Check for common truncation patterns
        truncation_patterns = [
            r'"answer_text":\s*"[^"]*$',  # Truncated in middle of answer_text
            r'"question_text":\s*"[^"]*$',  # Truncated in middle of question_text
            r'"explanation":\s*"[^"]*$',  # Truncated in middle of explanation
            r",\s*$",  # Ends with comma
            r":\s*$",  # Ends with colon
        ]

        for pattern in truncation_patterns:
            if re.search(pattern, content):
                logger.warning(f"Truncation pattern detected: {pattern}")
                return True

        return False
