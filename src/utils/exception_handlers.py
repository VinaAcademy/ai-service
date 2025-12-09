import logging

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from src.schemas.generic import ApiResponse
from src.utils.exceptions import (
    BadRequestException,
    ResourceNotFoundException,
    AccessDeniedException,
    UnauthorizedException,
)

logger = logging.getLogger(__name__)


def register_exception_handlers(app: FastAPI):
    """
    Register global exception handlers for the FastAPI app.
    Maps exceptions to ApiResponse with localized error messages (if implemented).
    """

    @app.exception_handler(BadRequestException)
    async def bad_request_handler(request: Request, exc: BadRequestException):
        logger.error(f"BadRequestException: {exc.message}", exc_info=True)
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=ApiResponse.error(
                code=status.HTTP_400_BAD_REQUEST, message=exc.message
            ).model_dump(mode="json"),
        )

    @app.exception_handler(ResourceNotFoundException)
    async def resource_not_found_handler(
            request: Request, exc: ResourceNotFoundException
    ):
        logger.error(f"ResourceNotFoundException: {exc.message}", exc_info=True)
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content=ApiResponse.error(
                code=status.HTTP_404_NOT_FOUND, message=exc.message
            ).model_dump(mode="json"),
        )

    @app.exception_handler(AccessDeniedException)
    async def access_denied_handler(request: Request, exc: AccessDeniedException):
        logger.error(f"AccessDeniedException: {exc.message}", exc_info=True)
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content=ApiResponse.error(
                code=status.HTTP_403_FORBIDDEN, message=exc.message
            ).model_dump(mode="json"),
        )

    @app.exception_handler(UnauthorizedException)
    async def unauthorized_handler(request: Request, exc: UnauthorizedException):
        logger.error(f"UnauthorizedException: {exc.message}", exc_info=True)
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content=ApiResponse.error(
                code=status.HTTP_401_UNAUTHORIZED, message=exc.message
            ).model_dump(mode="json"),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
            request: Request, exc: RequestValidationError
    ):
        logger.error(f"Validation error: {exc.errors()}", exc_info=True)
        # Extract validation errors
        errors = []
        for error in exc.errors():
            field = (
                ".".join(str(x) for x in error["loc"]) if error["loc"] else "unknown"
            )
            msg = error["msg"]
            errors.append(f"{field}: {msg}")

        message = ", ".join(errors)
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=ApiResponse.error(
                code=status.HTTP_400_BAD_REQUEST, message=f"Validation Error: {message}"
            ).model_dump(mode="json"),
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException):
        logger.error(f"HTTPException: {exc.detail}", exc_info=True)
        return JSONResponse(
            status_code=exc.status_code,
            content=ApiResponse.error(
                code=exc.status_code, message=str(exc.detail)
            ).model_dump(mode="json"),
        )

    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        logger.error(f"Unhandled Exception: {str(exc)}", exc_info=True)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=ApiResponse.error(
                code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                message="Internal Server Error",
            ).model_dump(mode="json"),
        )
