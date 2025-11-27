"""
Quiz Repository - Data access layer for quiz-related entities
"""
from typing import List, Optional, Sequence
from uuid import UUID, uuid4

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.model.course_models import Lesson
from src.model.quiz_models import Quiz, Question, Answer
from src.model.enums import LessonType, QuestionType
from src.repositories.base_repo import BaseRepository


class QuizRepository(BaseRepository[Lesson]):
    """
    Repository for Quiz entities (Lessons with type QUIZ).
    
    In the Java entity model, Quiz is a subtype of Lesson with lesson_type = QUIZ.
    This repository provides quiz-specific queries.
    """

    def __init__(self, session: AsyncSession):
        super().__init__(Lesson, session)

    async def get_quiz_by_id(
        self,
        quiz_id: UUID,
        include_deleted: bool = False
    ) -> Optional[Lesson]:
        """
        Get a quiz (lesson with type QUIZ) by ID.
        
        Args:
            quiz_id: UUID of the quiz lesson
            include_deleted: Whether to include soft-deleted records
            
        Returns:
            Lesson instance with type QUIZ or None if not found
        """
        query = (
            select(Lesson)
            .where(Lesson.id == quiz_id)
            .where(Lesson.lesson_type == LessonType.QUIZ)
        )
        
        if not include_deleted and hasattr(Lesson, 'is_deleted'):
            query = query.where(Lesson.is_deleted == False)
        
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def get_quizzes_by_section_id(
        self,
        section_id: UUID,
        include_deleted: bool = False
    ) -> Sequence[Lesson]:
        """
        Get all quizzes for a specific section.
        
        Args:
            section_id: UUID of the section
            include_deleted: Whether to include soft-deleted records
            
        Returns:
            List of Lesson instances with type QUIZ
        """
        query = (
            select(Lesson)
            .where(Lesson.section_id == section_id)
            .where(Lesson.lesson_type == LessonType.QUIZ)
            .order_by(Lesson.order_index)
        )
        
        if not include_deleted and hasattr(Lesson, 'is_deleted'):
            query = query.where(Lesson.is_deleted == False)
        
        result = await self.session.execute(query)
        return result.scalars().all()

    async def get_all_quizzes(
        self,
        skip: int = 0,
        limit: int = 100,
        include_deleted: bool = False
    ) -> Sequence[Lesson]:
        """
        Get all quizzes with pagination.
        
        Args:
            skip: Number of records to skip
            limit: Maximum number of records to return
            include_deleted: Whether to include soft-deleted records
            
        Returns:
            List of Lesson instances with type QUIZ
        """
        query = (
            select(Lesson)
            .where(Lesson.lesson_type == LessonType.QUIZ)
            .order_by(Lesson.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        
        if not include_deleted and hasattr(Lesson, 'is_deleted'):
            query = query.where(Lesson.is_deleted == False)
        
        result = await self.session.execute(query)
        return result.scalars().all()

    async def count_quizzes(self, include_deleted: bool = False) -> int:
        """
        Count total quiz lessons.
        
        Args:
            include_deleted: Whether to include soft-deleted records
            
        Returns:
            Total count of quizzes
        """
        query = (
            select(func.count(Lesson.id))
            .where(Lesson.lesson_type == LessonType.QUIZ)
        )
        
        if not include_deleted and hasattr(Lesson, 'is_deleted'):
            query = query.where(Lesson.is_deleted == False)
        
        result = await self.session.execute(query)
        return result.scalar() or 0

    async def get_quiz_details_by_lesson_id(
        self,
        lesson_id: UUID,
        include_deleted: bool = False
    ) -> Optional[Quiz]:
        """
        Get Quiz entity (with questions and answers) by lesson ID.
        
        Args:
            lesson_id: UUID of the lesson (same as quiz.id)
            include_deleted: Whether to include soft-deleted records
            
        Returns:
            Quiz instance with questions and answers loaded, or None
        """
        query = (
            select(Quiz)
            .options(
                selectinload(Quiz.questions).selectinload(Question.answers)
            )
            .where(Quiz.id == lesson_id)
        )
        
        if not include_deleted and hasattr(Quiz, 'is_deleted'):
            query = query.where(Quiz.is_deleted == False)
        
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def create_or_get_quiz_details(
        self,
        lesson_id: UUID
    ) -> Quiz:
        """
        Get existing Quiz entity or create a new one for the lesson.
        
        Args:
            lesson_id: UUID of the lesson (must be a QUIZ type lesson)
            
        Returns:
            Quiz instance (existing or newly created)
        """
        # Try to get existing quiz details
        quiz = await self.get_quiz_details_by_lesson_id(lesson_id)
        
        if quiz:
            return quiz
        
        # Create new Quiz entity (id is same as lesson_id)
        quiz = Quiz(
            id=lesson_id,
            total_points=0.0,
            duration=0,
            randomize_questions=False,
            show_correct_answers=True,
            allow_retake=True,
            require_passing_score=True,
            passing_score=70.0,
            time_limit=0
        )
        
        self.session.add(quiz)
        await self.session.flush()
        
        return quiz

    async def save_questions_to_quiz(
        self,
        lesson_id: UUID,
        questions_data: List[dict]
    ) -> Quiz:
        """
        Save generated questions to a quiz.
        
        Args:
            lesson_id: UUID of the quiz lesson
            questions_data: List of question dicts with format:
                {
                    "question_text": str,
                    "explanation": str | None,
                    "point": float,
                    "question_type": str,
                    "answers": [
                        {"answer_text": str, "is_correct": bool},
                        ...
                    ]
                }
                
        Returns:
            Quiz instance with saved questions
        """
        # Get or create quiz details
        quiz = await self.create_or_get_quiz_details(lesson_id)
        
        # Clear existing questions (replace with new ones)
        quiz.questions.clear()
        
        total_points = 0.0
        
        # Create Question and Answer entities
        for q_data in questions_data:
            question = Question(
                id=uuid4(),
                quiz_id=quiz.id,
                question_text=q_data["question_text"],
                explanation=q_data.get("explanation"),
                point=q_data.get("point", 1.0),
                question_type=QuestionType(q_data["question_type"])
            )
            
            total_points += question.point
            
            # Create answers for this question
            for ans_data in q_data.get("answers", []):
                answer = Answer(
                    id=uuid4(),
                    question_id=question.id,
                    answer_text=ans_data["answer_text"],
                    is_correct=ans_data.get("is_correct", False)
                )
                question.answers.append(answer)
            
            quiz.questions.append(question)
        
        # Update total points
        quiz.total_points = total_points
        
        await self.session.flush()
        
        return quiz

    async def commit(self):
        """Commit the current transaction."""
        await self.session.commit()
