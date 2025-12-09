"""
Course-related models matching Java entities
"""

from decimal import Decimal

from sqlalchemy import (
    Column,
    String,
    Text,
    Numeric,
    Enum as SQLEnum,
    Float,
    BigInteger,
    Integer,
    Boolean,
    ForeignKey,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import relationship

from src.model.base import Base, BaseMixin
from src.model.enums import CourseLevel, CourseStatus, LessonType


class Course(Base, BaseMixin):
    """
    Course model matching Java Course entity
    """

    __tablename__ = "courses"

    id = Column(PGUUID(as_uuid=True), primary_key=True)
    image = Column(String(255), nullable=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    slug = Column(String(255), unique=True, nullable=False, index=True)
    price = Column(Numeric(precision=10, scale=2), default=Decimal("0.00"))
    level = Column(
        SQLEnum(CourseLevel, name="course_level"),
        default=CourseLevel.BEGINNER,
        nullable=False,
    )
    status = Column(
        SQLEnum(CourseStatus, name="course_status"),
        default=CourseStatus.DRAFT,
        nullable=False,
    )
    language = Column(String(50), default="Tiếng Việt")
    category_id = Column(PGUUID(as_uuid=True), nullable=True)
    rating = Column(Float, default=0.0)
    total_rating = Column(BigInteger, default=0)
    total_student = Column(BigInteger, default=0)
    total_section = Column(BigInteger, default=0)
    total_lesson = Column(BigInteger, default=0)

    # Relationships
    sections = relationship(
        "Section",
        back_populates="course",
        cascade="all, delete-orphan",
        order_by="Section.order_index",
    )

    def __repr__(self):
        return f"<Course(id={self.id}, name={self.name})>"


class Section(Base, BaseMixin):
    """
    Section model matching Java Section entity
    """

    __tablename__ = "sections"

    id = Column(PGUUID(as_uuid=True), primary_key=True)
    course_id = Column(
        PGUUID(as_uuid=True),
        ForeignKey("courses.id", ondelete="CASCADE"),
        nullable=False,
    )
    title = Column(String(255), nullable=False)
    order_index = Column(Integer, default=0)

    # Relationships
    course = relationship("Course", back_populates="sections")
    lessons = relationship(
        "Lesson",
        back_populates="section",
        cascade="all, delete-orphan",
        order_by="Lesson.order_index",
    )

    def __repr__(self):
        return f"<Section(id={self.id}, title={self.title})>"


class Lesson(Base, BaseMixin):
    """
    Lesson model matching Java Lesson entity (abstract base)
    """

    __tablename__ = "lessons"

    id = Column(PGUUID(as_uuid=True), primary_key=True)
    section_id = Column(
        PGUUID(as_uuid=True),
        ForeignKey("sections.id", ondelete="CASCADE"),
        nullable=False,
    )
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    lesson_type = Column(String(31), default=LessonType.READING, nullable=False)
    is_free = Column(Boolean, default=False)
    order_index = Column(Integer, default=0)
    author_id = Column(PGUUID(as_uuid=True), nullable=False)
    version = Column(BigInteger, default=0)

    # Relationships
    section = relationship("Section", back_populates="lessons")

    def __repr__(self):
        return f"<Lesson(id={self.id}, title={self.title}, type={self.lesson_type})>"


class CourseInstructor(Base, BaseMixin):
    """
    CourseInstructor model matching Java CourseInstructor entity
    """

    __tablename__ = "course_instructor"

    id = Column(PGUUID(as_uuid=True), primary_key=True)
    course_id = Column(
        PGUUID(as_uuid=True),
        ForeignKey("courses.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id = Column(PGUUID(as_uuid=True), nullable=False)
    is_owner = Column(Boolean, default=False)

    def __repr__(self):
        return f"<CourseInstructor(id={self.id}, course_id={self.course_id}, instructor_id={self.user_id})>"
