"""
Enums matching Java entity enums
"""
from enum import Enum


class CourseLevel(str, Enum):
    """Course difficulty level"""
    BEGINNER = "BEGINNER"
    INTERMEDIATE = "INTERMEDIATE"
    ADVANCED = "ADVANCED"


class CourseStatus(str, Enum):
    """Course publication status"""
    DRAFT = "DRAFT"
    PENDING = "PENDING"
    PUBLISHED = "PUBLISHED"
    REJECTED = "REJECTED"

    @property
    def value_vi(self) -> str:
        """Vietnamese translation of the status"""
        translations = {
            "DRAFT": "bản nháp",
            "PENDING": "chờ duyệt",
            "PUBLISHED": "đã duyệt",
            "REJECTED": "bị từ chối"
        }
        return translations.get(self.value, self.value)


class LessonType(str, Enum):
    """Type of lesson content"""
    VIDEO = "VIDEO"
    READING = "READING"
    QUIZ = "QUIZ"


class QuestionType(str, Enum):
    """Type of quiz question"""
    SINGLE_CHOICE = "SINGLE_CHOICE"
    MULTIPLE_CHOICE = "MULTIPLE_CHOICE"
    TRUE_FALSE = "TRUE_FALSE"

    def is_single_choice(self) -> bool:
        return self == QuestionType.SINGLE_CHOICE

    def is_multiple_choice(self) -> bool:
        return self == QuestionType.MULTIPLE_CHOICE

    def is_true_false(self) -> bool:
        return self == QuestionType.TRUE_FALSE
