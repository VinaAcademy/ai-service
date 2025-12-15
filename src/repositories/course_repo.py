"""
Course Repository - Data access layer for courses
"""

from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.model.course_models import Course, Section, Lesson
from src.repositories.base_repo import BaseRepository


class CourseRepository(BaseRepository[Course]):
    """
    Repository for Course entity
    """

    def __init__(self, session: AsyncSession):
        super().__init__(Course, session)

    async def get_course_details(self, course_id: UUID) -> Optional[dict]:
        """
        Get course details with sections and lessons.

        Args:
            course_id: UUID of the course

        Returns:
            Dictionary with course details including sections and lessons
        """
        query = (
            select(Course)
            .options(
                selectinload(Course.sections).selectinload(Section.lessons)
            )
            .where(Course.id == course_id)
        )

        result = await self.session.execute(query)
        course = result.scalar_one_or_none()

        if not course:
            return None

        return {
            "course_id": course.id,
            "course_name": course.name,
            "course_description": course.description,
            "course_level": course.level.value if course.level else None,
            "course_language": course.language,
            "price": float(course.price) if course.price else 0.0,
            "rating": course.rating,
            "total_student": course.total_student,
            "sections": [
                {
                    "title": section.title,
                    "lessons": [
                        {
                            "title": lesson.title,
                            "type": lesson.lesson_type
                        }
                        for lesson in section.lessons
                    ]
                }
                for section in course.sections
            ]
        }
