from fastapi import HTTPException, status


class ChatbotException(Exception):
    """Base exception cho chatbot service"""
    pass


class LLMException(ChatbotException):
    """Exception khi gọi LLM"""
    pass


class DatabaseException(ChatbotException):
    """Exception liên quan database"""
    pass


# HTTP Exceptions cho FastAPI
def not_found_exception(detail: str = "Resource not found"):
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=detail)


def bad_request_exception(detail: str = "Bad request"):
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)


def internal_server_exception(detail: str = "Internal server error"):
    return HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=detail)
