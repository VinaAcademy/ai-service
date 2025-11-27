"""
Model package - Database models and enums
"""
from src.model.base import Base, BaseMixin, TimestampMixin, SoftDeleteMixin
from src.model.enums import CourseLevel, CourseStatus, LessonType, QuestionType
from src.model.course_models import Course, Section, Lesson
from src.model.quiz_models import Quiz, Question, Answer

__all__ = [
    # Base classes
    'Base',
    'BaseMixin',
    'TimestampMixin',
    'SoftDeleteMixin',
    # Enums
    'CourseLevel',
    'CourseStatus',
    'LessonType',
    'QuestionType',
    # Course models
    'Course',
    'Section',
    'Lesson',
    # Quiz models
    'Quiz',
    'Question',
    'Answer',
]