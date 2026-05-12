from sqlalchemy import Boolean, Column, Date, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Date, Time, Text, ForeignKey, Float
from sqlalchemy.sql import func
from app.database import Base


class Student(Base):
    __tablename__ = "students"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(120), nullable=False)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)

    study_hours_per_day = Column(Float, nullable=True)
    exam_days_left = Column(Integer, nullable=True)
    profile_completed = Column(Boolean, default=False)

    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class OTPVerification(Base):
    __tablename__ = "otp_verifications"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False)
    email = Column(String(255), nullable=False, index=True)

    otp_hash = Column(String(255), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    is_used = Column(Boolean, default=False)
    attempts = Column(Integer, default=0)

    created_at = Column(DateTime(timezone=True), server_default=func.now())


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
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False, index=True)
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
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False, index=True)
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

    student_id = Column(Integer, ForeignKey("students.id"), nullable=False, index=True)
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
    last_decay_at = Column(DateTime(timezone=True), server_default=func.now())
    last_activity_at = Column(DateTime(timezone=True), server_default=func.now())
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

class DailySchedule(Base):
    __tablename__ = "daily_schedule"

    id = Column(Integer, primary_key=True, index=True)

    student_id = Column(Integer, ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    schedule_date = Column(Date, nullable=False)

    subject_id = Column(Integer, ForeignKey("subjects.id", ondelete="CASCADE"), nullable=True)
    chapter_id = Column(Integer, ForeignKey("chapters.id", ondelete="CASCADE"), nullable=True)
    topic_id = Column(Integer, ForeignKey("chapter_topics.id", ondelete="SET NULL"), nullable=True)

    section = Column(String(30), default="STUDY")  # STUDY / REVISION
    task_type = Column(String(30), default="STUDY_NEW")  # STUDY_NEW / REVISION / RETEST / CATCH_UP
    schedule_title = Column(String(255), nullable=True)

    planned_minutes = Column(Integer, default=30)
    start_time = Column(Time, nullable=True)
    end_time = Column(Time, nullable=True)

    status = Column(String(30), default="SCHEDULED")  # SCHEDULED / COMPLETED / MISSED
    reason = Column(Text, nullable=True)

    carried_from_schedule_id = Column(Integer, nullable=True)
    carry_count = Column(Integer, default=0)

    completed_at = Column(DateTime(timezone=True), nullable=True)
class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True)

    student_id = Column(Integer, ForeignKey("students.id"), nullable=False, index=True)
    chapter_id = Column(Integer, ForeignKey("chapters.id"), nullable=True)

    notification_type = Column(String(50), default="WEAK_RETENTION")
    title = Column(String(255), nullable=False)
    message = Column(Text, nullable=False)

    retention = Column(Float, default=0)
    priority_score = Column(Float, default=0)

    is_read = Column(Boolean, default=False)
    email_sent = Column(Boolean, default=False)
    last_email_sent_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
# Add this model in models.py

class ChapterTopic(Base):
    __tablename__ = "chapter_topics"

    id = Column(Integer, primary_key=True, index=True)
    subject_id = Column(Integer, ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False)
    chapter_id = Column(Integer, ForeignKey("chapters.id", ondelete="CASCADE"), nullable=False)

    topic_name = Column(String(255), nullable=False)
    topic_order = Column(Integer, nullable=False)
    estimated_minutes = Column(Integer, default=30)
    difficulty = Column(String(30), default="Medium")
    is_active = Column(Boolean, default=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())