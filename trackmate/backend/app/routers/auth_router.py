from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_student
from app.models import Student
from app.schemas import (
    LoginRequest,
    SetupProfileRequest,
    SignupRequest,
    TokenResponse,
    VerifyOTPRequest,
)
from app.services.auth_service import request_login_otp, signup_student, verify_login_otp

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/signup")
def signup(request: SignupRequest, db: Session = Depends(get_db)):
    student = signup_student(
        db=db,
        name=request.name,
        email=request.email,
        password=request.password,
    )

    return {
        "message": "Signup successful. Please login now.",
        "student_id": student.id,
        "email": student.email,
    }


@router.post("/login")
def login(request: LoginRequest, db: Session = Depends(get_db)):
    return request_login_otp(
        db=db,
        email=request.email,
        password=request.password,
    )


@router.post("/verify-otp", response_model=TokenResponse)
def verify_otp(request: VerifyOTPRequest, db: Session = Depends(get_db)):
    return verify_login_otp(
        db=db,
        email=request.email,
        otp=request.otp,
    )


@router.get("/me")
def me(current_student: Student = Depends(get_current_student)):
    return {
        "id": current_student.id,
        "name": current_student.name,
        "email": current_student.email,
        "study_hours_per_day": current_student.study_hours_per_day,
        "exam_days_left": current_student.exam_days_left,
        "profile_completed": current_student.profile_completed,
    }


@router.post("/setup-profile")
def setup_profile(
    request: SetupProfileRequest,
    current_student: Student = Depends(get_current_student),
    db: Session = Depends(get_db),
):
    current_student.study_hours_per_day = request.study_hours_per_day
    current_student.exam_days_left = request.exam_days_left
    current_student.profile_completed = True

    db.commit()
    db.refresh(current_student)

    return {
        "message": "Profile setup completed",
        "student": {
            "id": current_student.id,
            "name": current_student.name,
            "email": current_student.email,
            "study_hours_per_day": current_student.study_hours_per_day,
            "exam_days_left": current_student.exam_days_left,
            "profile_completed": current_student.profile_completed,
        },
    }


@router.post("/logout")
def logout():
    return {
        "message": "Logout successful. Please clear token on frontend."
    }