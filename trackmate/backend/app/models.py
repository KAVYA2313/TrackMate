from sqlalchemy import Boolean, Column, Date, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class Subject(Base):
    __tablename__ = "subjects"

    id = Column(Integer, primary_key=True, index=True)
    subject_name = Column(String(100), unique=True, nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    chapters = relationship("Chapter", back_populates="subject")


class Chapter(Base):
    __tablename__ = "chapters"

    id = Column(Integer, primary_key=True, index=True)
    subject_id = Column(Integer, ForeignKey("subjects.id"), nullable=False)
    chapter_name = Column(String(255), nullable=False, index=True)
    chapter_order = Column(Integer, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    subject = relationship("Subject", back_populates="chapters")


class Question(Base):
    __tablename__ = "questions"

    id = Column(Integer, primary_key=True, index=True)
    subject_id = Column(Integer, ForeignKey("subjects.id"), nullable=False)
    chapter_id = Column(Integer, ForeignKey("chapters.id"), nullable=False)
    question_text = Column(Text, nullable=False)
    option_a = Column(String(255), nullable=False)
    option_b = Column(String(255), nullable=False)
    option_c = Column(String(255), nullable=False)
    option_d = Column(String(255), nullable=False)
    correct_answer = Column(String(1), nullable=False)
    difficulty = Column(String(30), default="Easy")
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Test(Base):
    __tablename__ = "tests"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, nullable=False, index=True)
    subject_id = Column(Integer, ForeignKey("subjects.id"), nullable=False)
    total_questions = Column(Integer, default=0)
    obtained_marks = Column(Float, default=0)
    total_marks = Column(Float, default=0)
    percentage = Column(Float, default=0)
    status = Column(String(30), default="GENERATED")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    submitted_at = Column(DateTime(timezone=True), nullable=True)


class TestQuestion(Base):
    __tablename__ = "test_questions"

    id = Column(Integer, primary_key=True, index=True)
    test_id = Column(Integer, ForeignKey("tests.id"), nullable=False, index=True)
    question_id = Column(Integer, ForeignKey("questions.id"), nullable=False)
    chapter_id = Column(Integer, ForeignKey("chapters.id"), nullable=False)


class TestAnswer(Base):
    __tablename__ = "test_answers"

    id = Column(Integer, primary_key=True, index=True)
    test_id = Column(Integer, ForeignKey("tests.id"), nullable=False, index=True)
    question_id = Column(Integer, ForeignKey("questions.id"), nullable=False)
    selected_answer = Column(String(1), nullable=False)
    correct_answer = Column(String(1), nullable=False)
    is_correct = Column(Boolean, default=False)


class StudentChapterProgress(Base):
    __tablename__ = "student_chapter_progress"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, nullable=False, index=True)
    subject_id = Column(Integer, ForeignKey("subjects.id"), nullable=False)
    chapter_id = Column(Integer, ForeignKey("chapters.id"), nullable=False)
    last_score = Column(Float, default=0)
    retention = Column(Float, default=0)
    memory_loss = Column(Float, default=100)
    test_count = Column(Integer, default=0)
    status = Column(String(30), default="NOT_STARTED")
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class RetentionState(Base):
    __tablename__ = "retention_states"

    id = Column(Integer, primary_key=True, index=True)

    student_id = Column(Integer, nullable=False, index=True)
    subject_id = Column(Integer, ForeignKey("subjects.id"), nullable=False)
    chapter_id = Column(Integer, ForeignKey("chapters.id"), nullable=False)

    subject = Column(String(100), nullable=False)
    chapter_name = Column(String(255), nullable=False)
    difficulty = Column(String(30), default="Medium")

    stability = Column(Float, default=5)
    revision_count = Column(Integer, default=0)
    last_score = Column(Float, default=0)
    retention = Column(Float, default=0)

    weak_chapter = Column(Boolean, default=False)
    priority_score = Column(Float, default=0)

    last_activity_at = Column(DateTime(timezone=True), server_default=func.now())
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class DailySchedule(Base):
    __tablename__ = "daily_schedule"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, nullable=False, index=True)
    schedule_date = Column(Date, nullable=False, index=True)
    subject_id = Column(Integer, ForeignKey("subjects.id"), nullable=False)
    chapter_id = Column(Integer, ForeignKey("chapters.id"), nullable=False)
    task_type = Column(String(30), nullable=False)
    planned_minutes = Column(Integer, default=60)
    status = Column(String(30), default="SCHEDULED")
    reason = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())