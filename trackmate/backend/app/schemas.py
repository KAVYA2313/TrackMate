from datetime import date
from typing import List, Optional

from pydantic import BaseModel, EmailStr, Field


class SignupRequest(BaseModel):
    name: str = Field(min_length=2)
    email: EmailStr
    password: str = Field(min_length=6)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class VerifyOTPRequest(BaseModel):
    email: EmailStr
    otp: str = Field(min_length=6, max_length=6)


class SetupProfileRequest(BaseModel):
    study_hours_per_day: float = Field(gt=0, le=16)
    exam_days_left: int = Field(gt=0, le=365)


class StudentResponse(BaseModel):
    id: int
    name: str
    email: str
    study_hours_per_day: Optional[float]
    exam_days_left: Optional[int]
    profile_completed: bool

    class Config:
        from_attributes = True


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    profile_completed: bool
    student: StudentResponse


class SubjectCreate(BaseModel):
    subject_name: str


class ChapterCreate(BaseModel):
    subject_id: int
    chapter_name: str
    chapter_order: int


class CreateQuestionRequest(BaseModel):
    subject_id: int
    chapter_id: int
    question_text: str
    option_a: str
    option_b: str
    option_c: str
    option_d: str
    correct_answer: str
    difficulty: str = "Easy"


class GenerateTestRequest(BaseModel):
    student_id: Optional[int] = None
    subject_id: int
    chapter_ids: List[int]
    question_count: int
    difficulty: str = "Easy"


class AnswerItem(BaseModel):
    question_id: int
    selected_answer: str = Field(pattern="^[A-Da-d]$")


class SubmitTestRequest(BaseModel):
    answers: List[AnswerItem]


class GenerateScheduleRequest(BaseModel):
    student_id: Optional[int] = None
    subject_id: int = 1
    start_date: Optional[date] = None
    days: int = Field(default=7, ge=1, le=14)
    daily_minutes: int = Field(default=120, ge=30, le=480)


class MarkScheduleRequest(BaseModel):
    status: str = Field(pattern="^(COMPLETED|MISSED)$")