"""
Lesson Repository - Data access layer for lessons with course/section context
"""
from typing import Optional, Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from src.model.course_models import Course, Section, Lesson
from src.repositories.base_repo import BaseRepository


class LessonRepository(BaseRepository[Lesson]):
    """
    Repository for Lesson entity with course/section context queries
    """

    def __init__(self, session: AsyncSession):
        super().__init__(Lesson, session)

    async def get_by_id(
        self, 
        id: UUID, 
        include_deleted: bool = False
    ) -> Optional[Lesson]:
        """
        Get a lesson by ID (UUID).
        
        Args:
            id: UUID primary key
            include_deleted: Whether to include soft-deleted records
            
        Returns:
            Lesson instance or None if not found
        """
        query = select(self.model).where(self.model.id == id)
        
        if not include_deleted and hasattr(self.model, 'is_deleted'):
            query = query.where(self.model.is_deleted.is_(False))
        
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def get_lessons_by_section_id(
        self,
        section_id: UUID,
        include_deleted: bool = False
    ) -> Sequence[Lesson]:
        """
        Get all lessons for a specific section.
        
        Args:
            section_id: UUID of the section
            include_deleted: Whether to include soft-deleted records
            
        Returns:
            List of Lesson instances
        """
        query = (
            select(Lesson)
            .where(Lesson.section_id == section_id)
            .order_by(Lesson.order_index)
        )
        
        if not include_deleted and hasattr(Lesson, 'is_deleted'):
            query = query.where(Lesson.is_deleted.is_(False))
        
        result = await self.session.execute(query)
        return result.scalars().all()

    async def get_lessons_with_course_context(
        self,
        section_id: UUID,
        include_deleted: bool = False
    ) -> Sequence[dict]:
        """
        Get lessons by section ID with full course context.
        
        This method returns a joined result with course and section information:
        - course name, description, language, level
        - section title
        - lesson type, description
        
        Args:
            section_id: UUID of the section
            include_deleted: Whether to include soft-deleted records
            
        Returns:
            List of dictionaries with course, section, and lesson info
        
        SQL equivalent:
            SELECT c.name, c.description, c.language, c.level,
                   s.title, l.lesson_type, l.description
            FROM courses c
            JOIN sections s ON s.course_id = c.id
            LEFT JOIN lessons l ON l.section_id = s.id
            WHERE s.id = :section_id
        """
        query = (
            select(
                Course.name.label('course_name'),
                Course.description.label('course_description'),
                Course.language.label('course_language'),
                Course.level.label('course_level'),
                Section.title.label('section_title'),
                Lesson.lesson_type,
                Lesson.description.label('lesson_description'),
                Lesson.id.label('lesson_id'),
                Lesson.title.label('lesson_title'),
                Lesson.order_index.label('lesson_order')
            )
            .select_from(Course)
            .join(Section, Section.course_id == Course.id)
            .outerjoin(Lesson, Lesson.section_id == Section.id)
            .where(Section.id == section_id)
            .order_by(Lesson.order_index)
        )
        
        if not include_deleted:
            if hasattr(Course, 'is_deleted'):
                query = query.where(Course.is_deleted.is_(False))
            if hasattr(Section, 'is_deleted'):
                query = query.where(Section.is_deleted.is_(False))
            if hasattr(Lesson, 'is_deleted'):
                query = query.where((Lesson.is_deleted.is_(False)) | (Lesson.id.is_(None)))
        
        result = await self.session.execute(query)
        rows = result.all()
        
        return [
            {
                'course_name': row.course_name,
                'course_description': row.course_description,
                'course_language': row.course_language,
                'course_level': row.course_level.value if row.course_level else None,
                'section_title': row.section_title,
                'lesson_id': row.lesson_id,
                'lesson_title': row.lesson_title,
                'lesson_type': row.lesson_type.value if row.lesson_type else None,
                'lesson_description': row.lesson_description,
                'lesson_order': row.lesson_order
            }
            for row in rows
        ]

    async def get_lesson_with_section(
        self,
        lesson_id: UUID,
        include_deleted: bool = False
    ) -> Optional[Lesson]:
        """
        Get a lesson with its section eagerly loaded.
        
        Args:
            lesson_id: UUID of the lesson
            include_deleted: Whether to include soft-deleted records
            
        Returns:
            Lesson instance with section loaded or None
        """
        query = (
            select(Lesson)
            .options(joinedload(Lesson.section))
            .where(Lesson.id == lesson_id)
        )
        
        if not include_deleted and hasattr(Lesson, 'is_deleted'):
            query = query.where(Lesson.is_deleted.is_(False))
        
        result = await self.session.execute(query)
        return result.scalar_one_or_none()
