from pgvector.sqlalchemy import Vector
from sqlalchemy import String, Text, Integer, Float, Column
from sqlalchemy.dialects.postgresql import ARRAY

from src.model.base import BaseMixin, Base


class ChatHistory(Base, BaseMixin):
    __tablename__ = 'chat_histories'

    session_id = Column(String(36), nullable=False, index=True)
    user_id = Column(String(36), nullable=False, index=True)
    message = Column(String, nullable=False)
    response = Column(Text, nullable=False)

    def __repr__(self):
        return f"<ChatHistory(session_id={self.session_id})>"


class CourseDocument(Base, BaseMixin):
    """
    Model lưu trữ thông tin khóa học với vector embeddings cho RAG
    """
    __tablename__ = 'course_documents'

    # Course information
    course_id = Column(String(36), nullable=False, unique=True, index=True)
    course_name = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)
    category = Column(String(100), nullable=False, index=True)  # Python, JavaScript, Web Dev, etc.
    level = Column(String(50), nullable=False)  # Beginner, Intermediate, Advanced
    duration_hours = Column(Integer, nullable=True)
    instructor = Column(String(255), nullable=True)
    tags = Column(ARRAY(String), nullable=True)

    # Pricing
    price = Column(Float, nullable=True)
    discount_price = Column(Float, nullable=True)

    # Additional metadata
    prerequisites = Column(Text, nullable=True)
    learning_outcomes = Column(Text, nullable=True)
    syllabus = Column(Text, nullable=True)

    # Vector embedding for RAG
    embedding = Column(Vector(1536), nullable=True)  # OpenAI text-embedding-3-small dimension

    # Full text content for embedding (combination of all text fields)
    content = Column(Text, nullable=False)

    def __repr__(self):
        return f"<CourseDocument(course_id={self.course_id}, name={self.course_name})>"
