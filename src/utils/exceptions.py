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


class BadRequestException(ChatbotException):
    """Exception cho Bad Request (400)"""

    def __init__(self, message: str = "Bad Request"):
        self.message = message
        super().__init__(self.message)


class ResourceNotFoundException(ChatbotException):
    """Exception cho Not Found (404)"""

    def __init__(self, message: str = "Resource Not Found"):
        self.message = message
        super().__init__(self.message)


class AccessDeniedException(ChatbotException):
    """Exception cho Forbidden (403)"""

    def __init__(self, message: str = "Access Denied"):
        self.message = message
        super().__init__(self.message)


class UnauthorizedException(ChatbotException):
    """Exception cho Unauthorized (401)"""

    def __init__(self, message: str = "Unauthorized"):
        self.message = message
        super().__init__(self.message)


# HTTP Exceptions cho FastAPI
def not_found_exception(detail: str = "Resource not found"):
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=detail)


def bad_request_exception(detail: str = "Bad request"):
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)


def internal_server_exception(detail: str = "Internal server error"):
    return HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=detail)
