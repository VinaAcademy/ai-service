"""
Quiz-related models matching Java entities (Quiz, Question, Answer)
"""

from sqlalchemy import (
    Column, Text, Float, Integer, Boolean, ForeignKey, String
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import relationship

from src.model.base import Base, BaseMixin
from src.model.enums import QuestionType


class Quiz(Base):
    """
    Quiz model matching Java Quiz entity.
    
    Quiz extends Lesson in Java (using Single Table Inheritance with discriminator 'QUIZ').
    The Quiz ID is the same as the Lesson ID (shared primary key pattern).
    """
    __tablename__ = 'quiz'

    # Primary key is same as lesson.id (shared primary key)
    id = Column(
        PGUUID(as_uuid=True),
        ForeignKey('lessons.id', ondelete='CASCADE'),
        primary_key=True
    )

    # Quiz-specific fields
    total_points = Column('total_point', Float, default=0.0)
    duration = Column(Integer, default=0)

    # Quiz settings
    randomize_questions = Column(Boolean, default=False)
    show_correct_answers = Column(Boolean, default=True)
    allow_retake = Column(Boolean, default=True)
    require_passing_score = Column(Boolean, default=True)
    passing_score = Column(Float, default=70.0)
    time_limit = Column(Integer, default=0)  # in minutes, 0 means no limit

    # Relationships
    lesson = relationship("Lesson", backref="quiz_details", uselist=False)
    questions = relationship(
        "Question",
        back_populates="quiz",
        cascade="all, delete-orphan",
        lazy="selectin"
    )

    def add_question(self, question: "Question"):
        """Add a question to this quiz"""
        self.questions.append(question)
        question.quiz = self

    def remove_question(self, question: "Question"):
        """Remove a question from this quiz"""
        self.questions.remove(question)
        question.quiz = None

    def __repr__(self):
        return f"<Quiz(id={self.id})>"


class Question(Base, BaseMixin):
    """
    Question model matching Java Question entity.
    """
    __tablename__ = 'questions'

    id = Column(PGUUID(as_uuid=True), primary_key=True)

    quiz_id = Column(
        PGUUID(as_uuid=True),
        ForeignKey('quiz.id', ondelete='CASCADE'),
        nullable=False
    )

    question_text = Column(Text, nullable=False)
    explanation = Column(Text, nullable=True)
    point = Column(Float, default=1.0)
    question_type = Column(
        String,
        default=QuestionType.SINGLE_CHOICE,
        nullable=False
    )

    # Relationships
    quiz = relationship("Quiz", back_populates="questions")
    answers = relationship(
        "Answer",
        back_populates="question",
        cascade="all, delete-orphan",
        lazy="selectin"
    )

    def add_answer(self, answer: "Answer"):
        """Add an answer to this question"""
        self.answers.append(answer)
        answer.question = self

    def remove_answer(self, answer: "Answer"):
        """Remove an answer from this question"""
        self.answers.remove(answer)
        answer.question = None

    def __repr__(self):
        return f"<Question(id={self.id}, type={self.question_type})>"


class Answer(Base, BaseMixin):
    """
    Answer model matching Java Answer entity.
    """
    __tablename__ = 'answers'

    id = Column(PGUUID(as_uuid=True), primary_key=True)

    question_id = Column(
        PGUUID(as_uuid=True),
        ForeignKey('questions.id', ondelete='CASCADE'),
        nullable=False
    )

    answer_text = Column(Text, nullable=False)
    is_correct = Column(Boolean, default=False)

    # Relationships
    question = relationship("Question", back_populates="answers")

    def __repr__(self):
        return f"<Answer(id={self.id}, is_correct={self.is_correct})>"
