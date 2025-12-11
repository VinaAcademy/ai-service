"""
Redis client for distributed locking and progress tracking.

Features:
    - Distributed lock by quiz_id to prevent concurrent generation
    - Progress tracking with TTL (Time To Live)
    - Atomic operations for thread-safe updates
"""

import json
import logging
from contextlib import asynccontextmanager
from typing import Optional, Dict, Any

import redis.asyncio as redis
from redis.asyncio import Redis
from redis.exceptions import LockError

from src.config import Settings

logger = logging.getLogger(__name__)


class RedisClient:
    """Redis client for locking and progress tracking"""

    # TTL settings
    LOCK_TTL = 3600  # 1 hour lock timeout
    PROGRESS_TTL = 86400  # 24 hours progress tracking

    def __init__(self, settings: Settings):
        self._redis_url = settings.redis_url
        self._client: Optional[Redis] = None

    async def connect(self):
        """Establish Redis connection"""
        if not self._redis_url:
            logger.warning("Redis URL not configured, Redis features disabled")
            return

        try:
            self._client = redis.from_url(
                self._redis_url,
                encoding="utf-8",
                decode_responses=True
            )
            # Test connection
            await self._client.ping()
            logger.info("Redis connection established successfully")
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            self._client = None

    async def disconnect(self):
        """Close Redis connection"""
        if self._client:
            await self._client.close()
            logger.info("Redis connection closed")

    def is_available(self) -> bool:
        """Check if Redis is available"""
        return self._client is not None

    # =============================
    #   Distributed Lock
    # =============================
    def _lock_key(self, quiz_id: str) -> str:
        """Generate lock key for quiz_id"""
        return f"quiz:lock:{quiz_id}"

    @asynccontextmanager
    async def acquire_quiz_lock(self, quiz_id: str, timeout: int = LOCK_TTL):
        """
        Acquire distributed lock for quiz generation.

        Args:
            quiz_id: UUID string of the quiz
            timeout: Lock timeout in seconds

        Yields:
            True if lock acquired

        Raises:
            LockError: If lock cannot be acquired (quiz already being generated)
        """
        if not self.is_available():
            # If Redis is not available, allow operation (no locking)
            logger.warning("Redis not available, skipping lock")
            yield True
            return

        lock_key = self._lock_key(quiz_id)
        lock = self._client.lock(
            lock_key,
            timeout=timeout,
            blocking=False  # Don't wait, fail immediately if locked
        )

        try:
            # Try to acquire lock (non-blocking)
            acquired = await lock.acquire(blocking=False)
            if not acquired:
                raise LockError(f"Quiz {quiz_id} is already being generated")

            logger.info(f"Acquired lock for quiz {quiz_id}")
            yield True

        finally:
            # Release lock if we acquired it
            try:
                await lock.release()
                logger.info(f"Released lock for quiz {quiz_id}")
            except LockError:
                # Lock already released or expired
                pass

    # =============================
    #   Progress Tracking
    # =============================
    def _progress_key(self, quiz_id: str) -> str:
        """Generate progress key for quiz_id"""
        return f"quiz:progress:{quiz_id}"

    async def set_progress(
            self,
            quiz_id: str,
            status: str,
            progress: int,
            message: str,
            total_questions: int = 0,
            error: Optional[str] = None
    ):
        """
        Update quiz generation progress.

        Args:
            quiz_id: UUID string of the quiz
            status: Status string (PENDING, PROCESSING, COMPLETED, FAILED)
            progress: Progress percentage (0-100)
            message: Human-readable status message
            total_questions: Number of questions generated
            error: Error message if failed
        """
        if not self.is_available():
            logger.warning("Redis not available, skipping progress update")
            return

        progress_data = {
            "status": status,
            "progress": progress,
            "message": message,
            "total_questions": total_questions,
        }

        if error:
            progress_data["error"] = error

        progress_key = self._progress_key(quiz_id)

        try:
            # Store as JSON with TTL
            await self._client.setex(
                progress_key,
                self.PROGRESS_TTL,
                json.dumps(progress_data)
            )
            logger.debug(f"Updated progress for quiz {quiz_id}: {progress}%")
        except Exception as e:
            logger.error(f"Failed to update progress: {e}")

    async def get_progress(self, quiz_id: str) -> Optional[Dict[str, Any]]:
        """
        Get quiz generation progress.

        Args:
            quiz_id: UUID string of the quiz

        Returns:
            Progress dict or None if not found
        """
        if not self.is_available():
            return None

        progress_key = self._progress_key(quiz_id)

        try:
            data = await self._client.get(progress_key)
            if data:
                return json.loads(data)
            return None
        except Exception as e:
            logger.error(f"Failed to get progress: {e}")
            return None

    async def delete_progress(self, quiz_id: str):
        """
        Delete quiz generation progress.

        Args:
            quiz_id: UUID string of the quiz
        """
        if not self.is_available():
            return

        progress_key = self._progress_key(quiz_id)

        try:
            await self._client.delete(progress_key)
            logger.debug(f"Deleted progress for quiz {quiz_id}")
        except Exception as e:
            logger.error(f"Failed to delete progress: {e}")

    def ping(self):
        """Ping Redis server to check connectivity"""
        if self.is_available():
            return self._client.ping()
        return False
