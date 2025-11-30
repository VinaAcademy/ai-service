from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, Field


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
