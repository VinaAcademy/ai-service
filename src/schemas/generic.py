from datetime import datetime, timezone
from typing import Optional, TypeVar, Generic

from pydantic import BaseModel, Field

T = TypeVar("T")


class ApiResponse(BaseModel, Generic[T]):
    """Generic API Response following the Java structure"""
    status: str
    message: Optional[str] = None
    code: Optional[int] = None
    data: Optional[T] = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @classmethod
    def success(cls, data: Optional[T] = None, message: Optional[str] = None):
        return cls(
            status="SUCCESS",
            message=message,
            data=data,
            timestamp=datetime.now(timezone.utc)
        )

    @classmethod
    def error(cls, code: int, message: str, data: Optional[T] = None):
        return cls(
            status="ERROR",
            message=message,
            code=code,
            data=data,
            timestamp=datetime.now(timezone.utc)
        )


class HealthResponse(BaseModel):
    """Health check response"""
    status: str
    service: str
    version: str
    environment: str


class ErrorResponse(BaseModel):
    """Error response"""
    error: str
    detail: Optional[str] = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    class Config:
        json_schema_extra = {
            "example": {
                "error": "Bad Request",
                "detail": "Invalid session_id format",
                "timestamp": "2024-11-07T10:30:00Z"
            }
        }


class SuccessResponse(BaseModel):
    """Generic success response"""
    message: str
    data: Optional[dict] = None
